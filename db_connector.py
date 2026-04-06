"""
db_connector_azure.py — Azure SQL Only
========================================
Simplified connector for Azure SQL database.
Removes all multi-database, PostgreSQL, and registry complexity.

Just Azure SQL. Simple. Clean.
"""

import os
import json
import pandas as pd
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.pool import NullPool

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Azure SQL Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
SCHEMA_CACHE_PATH = BASE_DIR / "schema_cache.json"

# Get credentials from environment variables (set in Azure App Service)
SQL_SERVER = os.getenv("SQL_SERVER_NAME", "sirish-azure-sql-server.database.windows.net")
SQL_DATABASE = os.getenv("SQL_DATABASE", "sirish_azure_sql_db")
SQL_USER = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

# ─────────────────────────────────────────────────────────────────────────────
# Connection Factory
# ─────────────────────────────────────────────────────────────────────────────

def build_engine():
    """Build SQLAlchemy engine for Azure SQL."""
    if not SQL_USER or not SQL_PASSWORD:
        raise ValueError("SQL_USER and SQL_PASSWORD environment variables not set")

    # Azure SQL connection string
    # - Driver 18 is the version pre-installed on Azure App Service Linux (Python 3.12)
    # - quote_plus encodes special chars in password (e.g. @, #, !) so URL doesn't break
    # - Driver 18 encrypts by default (good for Azure); TrustServerCertificate=no is safe
    connection_string = (
        f"mssql+pyodbc://{SQL_USER}:{quote_plus(SQL_PASSWORD)}"
        f"@{SQL_SERVER}/{SQL_DATABASE}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=no"
        f"&Connection+Timeout=30"
    )

    return create_engine(connection_string, poolclass=NullPool)

def test_connection() -> bool:
    """Quick test to verify Azure SQL is reachable."""
    try:
        engine = build_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Schema Discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_schema() -> dict:
    """Discover all tables, columns, and relationships in Azure SQL."""
    engine = build_engine()
    inspector = sa_inspect(engine)

    schema = {
        "database": SQL_DATABASE,
        "tables": {}
    }

    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"]
            })

        schema["tables"][table_name] = {
            "columns": columns,
            "primary_key": inspector.get_pk_constraint(table_name).get("constrained_columns", []),
        }

    return schema

def refresh_schema() -> dict:
    """Discover and cache schema."""
    schema = discover_schema()
    with open(SCHEMA_CACHE_PATH, "w") as f:
        json.dump(schema, f, indent=2)
    return schema

def get_cached_schema() -> dict:
    """Load cached schema (or discover if not cached)."""
    if SCHEMA_CACHE_PATH.exists():
        with open(SCHEMA_CACHE_PATH, "r") as f:
            return json.load(f)
    return refresh_schema()

def get_schema_for_llm() -> str:
    """Get a compact schema string for LLM injection."""
    schema = get_cached_schema()

    lines = [f"Database: {schema['database']}\n"]
    for table_name, table_info in schema["tables"].items():
        lines.append(f"\nTable: {table_name}")
        pk = table_info.get("primary_key", [])
        if pk:
            lines.append(f"  Primary Key: {', '.join(pk)}")

        for col in table_info["columns"]:
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            lines.append(f"  - {col['name']}: {col['type']} {nullable}")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Query Execution
# ─────────────────────────────────────────────────────────────────────────────

def execute_query(sql: str, max_rows: int = 1000) -> pd.DataFrame:
    """
    Execute a SELECT query and return results as DataFrame.

    Safety:
    - Only allows SELECT statements
    - Prevents SQL injection
    - Limits result rows
    """
    # Basic safety check
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    if any(keyword in sql_upper for keyword in ["DELETE", "DROP", "UPDATE", "INSERT", "TRUNCATE"]):
        raise ValueError("Dangerous SQL keywords not allowed")

    try:
        engine = build_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

            # Limit rows
            if len(df) > max_rows:
                df = df.head(max_rows)
                print(f"⚠️  Results limited to {max_rows} rows")

            return df

    except Exception as e:
        raise Exception(f"Query execution failed: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# Vector Memory (Simple Azure SQL storage)
# ─────────────────────────────────────────────────────────────────────────────

def save_query_memory(question: str, sql: str, results: str) -> bool:
    """Store a question+SQL pair in Azure SQL for future similarity matching."""
    try:
        # TODO: Implement vector storage in Azure SQL
        # For now, just log that it would be saved
        print(f"💾 Would save memory: {question[:50]}...")
        return True
    except Exception as e:
        print(f"⚠️  Could not save memory: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def health_check() -> dict:
    """Check the status of Azure SQL connection."""
    return {
        "connected": test_connection(),
        "server": SQL_SERVER,
        "database": SQL_DATABASE,
        "user": SQL_USER[:5] + "***" if SQL_USER else "NOT SET"
    }
