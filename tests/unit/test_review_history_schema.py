from mr_guardian.models.history import review_run_record_schema


def test_review_run_record_schema_includes_latest_top_level_fields() -> None:
    schema = review_run_record_schema()

    properties = schema["properties"]

    assert schema["title"] == "ReviewRunRecord"
    assert "review_id" in properties
    assert "timestamp" in properties
    assert "review_scope" in properties
    assert "developer_id" in properties
    assert "ticket_key" in properties
    assert "review_score" in properties
    assert "generated_review_report" in properties


def test_review_run_record_schema_includes_evaluation_and_llm_fields() -> None:
    schema = review_run_record_schema()
    properties = schema["properties"]
    defs = schema["$defs"]

    assert "evaluations" in properties
    assert "llm_metrics" in properties
    assert "llm_summary" in properties
    assert "developer_profile" in properties
    assert "score" in defs["LlmReviewSummary"]["properties"]
    assert "lookback_days" in defs["LlmDeveloperProfile"]["properties"]


def test_review_run_record_schema_includes_sqlite_storage_notes() -> None:
    schema = review_run_record_schema()

    assert "llm_summary_score" in schema["x-sqlite-columns"]
    assert "developer_profile" in schema["x-sqlite-columns"]
    assert "project_name" in schema["x-storage-notes"]
    assert "llm_summary_score" in schema["x-storage-notes"]
