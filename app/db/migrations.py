from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_startup_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "teams" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("teams")}
    statements: list[str] = []

    if "average_age" not in existing_columns:
        statements.append("ALTER TABLE teams ADD COLUMN average_age VARCHAR(50) NOT NULL DEFAULT ''")
    if "region" not in existing_columns:
        statements.append("ALTER TABLE teams ADD COLUMN region VARCHAR(100) NOT NULL DEFAULT ''")
    if "genres" not in existing_columns:
        statements.append("ALTER TABLE teams ADD COLUMN genres TEXT NOT NULL DEFAULT '[]'")
    if "gender_ratio" not in existing_columns:
        statements.append("ALTER TABLE teams ADD COLUMN gender_ratio VARCHAR(50) NOT NULL DEFAULT ''")
    if "reference_songs" not in existing_columns:
        statements.append("ALTER TABLE teams ADD COLUMN reference_songs TEXT NOT NULL DEFAULT '[]'")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
