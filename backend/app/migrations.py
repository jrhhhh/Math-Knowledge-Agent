from sqlalchemy import inspect, text

SCHEMA_VERSION = 1

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
    connection.execute(text("INSERT OR IGNORE INTO schema_versions(version) VALUES (:version)"), {"version": SCHEMA_VERSION})
