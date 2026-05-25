"""GitLab API delivery helpers."""

from dataclasses import dataclass
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class GitLabApiError(Exception):
    """Raised when a GitLab API request fails."""


class UrlOpen(Protocol):
    """Callable compatible with urllib.request.urlopen for dependency injection."""

    def __call__(self, request: Request, *, timeout: float) -> object:
        """Open one HTTP request."""


@dataclass(frozen=True)
class GitLabMergeRequestCommenter:
    """Post generated review reports to GitLab Merge Requests."""

    base_url: str
    token: str
    timeout_seconds: float = 10.0
    opener: UrlOpen | None = None

    def post_merge_request_note(
        self,
        *,
        project_ref: str,
        merge_request_iid: str,
        body: str,
    ) -> None:
        """Post one note to a GitLab Merge Request."""
        if not self.token:
            msg = "GitLab token is required to post review comments."
            raise GitLabApiError(msg)
        if not project_ref:
            msg = "GitLab project reference is required to post review comments."
            raise GitLabApiError(msg)
        if not merge_request_iid:
            msg = "GitLab Merge Request IID is required to post review comments."
            raise GitLabApiError(msg)

        request = Request(
            self._merge_request_notes_url(
                project_ref=project_ref,
                merge_request_iid=merge_request_iid,
            ),
            data=urlencode({"body": body}).encode("utf-8"),
            headers={
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            opener = self.opener or cast(UrlOpen, urlopen)
            response = opener(request, timeout=self.timeout_seconds)
            close = getattr(response, "close", None)
            if callable(close):
                close()
        except HTTPError as exc:
            msg = f"GitLab API rejected review comment with status {exc.code}."
            raise GitLabApiError(msg) from exc
        except URLError as exc:
            msg = f"Could not reach GitLab API: {exc.reason}"
            raise GitLabApiError(msg) from exc
        except TimeoutError as exc:
            msg = "GitLab API request timed out while posting review comment."
            raise GitLabApiError(msg) from exc

    def _merge_request_notes_url(self, *, project_ref: str, merge_request_iid: str) -> str:
        base_url = self.base_url.rstrip("/")
        encoded_project = quote(project_ref, safe="")
        encoded_mr = quote(merge_request_iid, safe="")
        return f"{base_url}/api/v4/projects/{encoded_project}/merge_requests/{encoded_mr}/notes"
