from sqlalchemy import inspect, text

SCHEMA_VERSION = 9

def run_schema_migrations(connection):
    connection.execute(text("CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
    columns = {column["name"] for column in inspect(connection).get_columns("local_answer_template_events")}
    if "snapshot" not in columns:
        connection.execute(text("ALTER TABLE local_answer_template_events ADD COLUMN snapshot TEXT"))
    template_columns = {column["name"] for column in inspect(connection).get_columns("local_answer_templates")}
    if "review_status" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'approved'"))
    if "hit_count" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN hit_count INTEGER NOT NULL DEFAULT 0"))
    if "last_hit_at" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN last_hit_at DATETIME"))
    task_columns = {column["name"] for column in inspect(connection).get_columns("ai_task_statuses")}
    if "result_json" not in task_columns:
        connection.execute(text("ALTER TABLE ai_task_statuses ADD COLUMN result_json TEXT"))
    if "goal" not in task_columns:
        connection.execute(text("ALTER TABLE ai_task_statuses ADD COLUMN goal TEXT"))
    if "termination_reason" not in task_columns:
        connection.execute(text("ALTER TABLE ai_task_statuses ADD COLUMN termination_reason VARCHAR(120)"))
    if "evidence_summary" not in task_columns:
        connection.execute(text("ALTER TABLE ai_task_statuses ADD COLUMN evidence_summary TEXT"))
    graph_columns = {column["name"] for column in inspect(connection).get_columns("graph_candidates")}
    if "conversation_id" not in graph_columns:
        connection.execute(text("ALTER TABLE graph_candidates ADD COLUMN conversation_id INTEGER"))
    if "source_message_ids" not in graph_columns:
        connection.execute(text("ALTER TABLE graph_candidates ADD COLUMN source_message_ids TEXT DEFAULT '[]'"))
    retry_columns = {column["name"] for column in inspect(connection).get_columns("ai_retry_jobs")}
    if "conversation_id" not in retry_columns:
        connection.execute(text("ALTER TABLE ai_retry_jobs ADD COLUMN conversation_id INTEGER"))
    review_columns = {column["name"] for column in inspect(connection).get_columns("answer_reviews")}
    for column in ("correctness", "conclusion", "conditions", "reasoning", "citations"):
        if column not in review_columns:
            connection.execute(text(f"ALTER TABLE answer_reviews ADD COLUMN {column} VARCHAR(24) NOT NULL DEFAULT 'unverified'"))
    connection.execute(text("INSERT OR IGNORE INTO schema_versions(version) VALUES (:version)"), {"version": SCHEMA_VERSION})
