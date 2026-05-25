from http.client import HTTPMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from mr_guardian.providers.gitlab_api import GitLabApiError, GitLabMergeRequestCommenter


def test_posts_merge_request_note_to_gitlab_api() -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def close(self) -> None:
            captured["closed"] = True

    def fake_opener(request: Request, *, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = request.data
        captured["token"] = request.headers["Private-token"]
        captured["content_type"] = request.headers["Content-type"]
        return FakeResponse()

    commenter = GitLabMergeRequestCommenter(
        base_url="https://gitlab.example.com/",
        token="secret-token",
        timeout_seconds=3.5,
        opener=fake_opener,
    )

    commenter.post_merge_request_note(
        project_ref="team/MRGuardian",
        merge_request_iid="7",
        body="# MR Guardian Review",
    )

    assert captured["url"] == (
        "https://gitlab.example.com/api/v4/projects/team%2FMRGuardian/"
        "merge_requests/7/notes"
    )
    assert captured["timeout"] == 3.5
    assert captured["body"] == b"body=%23+MR+Guardian+Review"
    assert captured["token"] == "secret-token"
    assert captured["content_type"] == "application/x-www-form-urlencoded"
    assert captured["closed"] is True


def test_requires_gitlab_token_to_post_merge_request_note() -> None:
    commenter = GitLabMergeRequestCommenter(
        base_url="https://gitlab.example.com",
        token="",
    )

    with pytest.raises(GitLabApiError, match="token is required"):
        commenter.post_merge_request_note(
            project_ref="42",
            merge_request_iid="7",
            body="# MR Guardian Review",
        )


def test_reports_gitlab_http_errors() -> None:
    def fake_opener(request: Request, *, timeout: float) -> object:
        raise HTTPError(
            url=request.full_url,
            code=403,
            msg="Forbidden",
            hdrs=HTTPMessage(),
            fp=None,
        )

    commenter = GitLabMergeRequestCommenter(
        base_url="https://gitlab.example.com",
        token="secret-token",
        opener=fake_opener,
    )

    with pytest.raises(GitLabApiError, match="status 403"):
        commenter.post_merge_request_note(
            project_ref="42",
            merge_request_iid="7",
            body="# MR Guardian Review",
        )


def test_reports_gitlab_connection_errors() -> None:
    def fake_opener(request: Request, *, timeout: float) -> object:
        raise URLError("offline")

    commenter = GitLabMergeRequestCommenter(
        base_url="https://gitlab.example.com",
        token="secret-token",
        opener=fake_opener,
    )

    with pytest.raises(GitLabApiError, match="Could not reach GitLab API"):
        commenter.post_merge_request_note(
            project_ref="42",
            merge_request_iid="7",
            body="# MR Guardian Review",
        )
