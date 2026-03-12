from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_startup_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    statements: list[str] = []

    table_names = set(inspector.get_table_names())
    if "teams" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("teams")}
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

    if "users" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("users")}
        if "gender" not in existing_columns:
            statements.append("ALTER TABLE users ADD COLUMN gender VARCHAR(20)")
        if "age" not in existing_columns:
            statements.append("ALTER TABLE users ADD COLUMN age INTEGER")

    if "matching_profiles" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("matching_profiles")}
        if "profile_summary" not in existing_columns:
            statements.append("ALTER TABLE matching_profiles ADD COLUMN profile_summary VARCHAR(255)")

    if "team_matching_profiles" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("team_matching_profiles")}
        if "recruit_summary" not in existing_columns:
            statements.append("ALTER TABLE team_matching_profiles ADD COLUMN recruit_summary VARCHAR(255)")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
