"""
db_connector.py — Universal Database Connector
===============================================
Reads db_registry.yaml to connect to any supported database type.
Uses SQLAlchemy as a unified adapter across all backends.

Supports:
  - PostgreSQL, SQL Server, MySQL, SQLite, DuckDB
  - Snowflake, BigQuery, Oracle, Databricks, Redshift (when deps installed)

Key capabilities:
  - build_engine()       → SQLAlchemy engine for any registered DB
  - test_connection()    → quick ping test
  - discover_schema()    → auto-scrape tables, columns, PKs, FKs, views, procedures
  - refresh_schema()     → discover + write to schema_cache.json
  - get_schema_for_llm() → compact schema string for injection into LLM prompts
  - execute_query()      → safe SELECT-only execution returning a DataFrame
"""

import os
import json
import re       # Used for row-limit injection (finding SELECT/TOP/LIMIT keywords in SQL)
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool

load_dotenv()

BASE_DIR         = Path(__file__).parent
REGISTRY_PATH    = BASE_DIR / "db_registry.yaml"
SCHEMA_CACHE_PATH = BASE_DIR / "schema_cache.json"

# ─────────────────────────────────────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_registry() -> Dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_registry(registry: Dict):
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def get_all_databases() -> Dict[str, Dict]:
    return load_registry().get("databases", {})

def get_enabled_databases() -> Dict[str, Dict]:
    return {k: v for k, v in get_all_databases().items() if v.get("enabled", False)}

def get_domain_map() -> Dict[str, str]:
    """Returns {DOMAIN: db_key} for enabled DBs that have a domain set."""
    return {
        v["domain"].upper(): k
        for k, v in get_enabled_databases().items()
        if v.get("domain")
    }

# ─────────────────────────────────────────────────────────────────────────────
# Engine factory
# ─────────────────────────────────────────────────────────────────────────────

def _env(config: Dict, key: str, fallback_key: str = None) -> str:
    """Resolve a value: direct value → env var → empty string."""
    direct = config.get(fallback_key, "") if fallback_key else ""
    env_key = config.get(key, "")
    return os.getenv(env_key, direct) if env_key else direct

def build_engine(db_key: str, db_config: Dict) -> Engine:
    """Build and return a SQLAlchemy engine from a registry config entry."""
    t = db_config["type"]

    password = _env(db_config, "password_env", "password")
    username = db_config.get("username") or _env(db_config, "username_env")
    host     = _env(db_config, "host_env", "host") or "localhost"
    port     = db_config.get("port")
    database = db_config.get("database", "")

    # ── PostgreSQL ──────────────────────────────────────────────────────────
    if t == "postgresql":
        url = URL.create("postgresql+psycopg2",
                         username=username, password=password,
                         host=host, port=int(port or 5432), database=database)

    # ── SQL Server ──────────────────────────────────────────────────────────
    elif t == "mssql":
        try:
            import pyodbc
            drivers  = [d for d in pyodbc.drivers() if "SQL Server" in d]
            odbc_drv = [d for d in drivers if "ODBC Driver" in d]
            driver   = odbc_drv[-1] if odbc_drv else (drivers[-1] if drivers else "SQL Server")
        except Exception:
            driver = "SQL Server"

        query_params = {"driver": driver, "TrustServerCertificate": "yes"}
        if not username:
            query_params["Trusted_Connection"] = "yes"

        url = URL.create("mssql+pyodbc",
                         username=username or None,
                         password=password or None,
                         host=host, database=database,
                         query=query_params)

    # ── MySQL ───────────────────────────────────────────────────────────────
    elif t == "mysql":
        url = URL.create("mysql+pymysql",
                         username=username, password=password,
                         host=host, port=int(port or 3306), database=database)

    # ── SQLite ──────────────────────────────────────────────────────────────
    elif t == "sqlite":
        fp = db_config.get("file_path", ":memory:")
        return create_engine(f"sqlite:///{fp}", poolclass=NullPool)

    # ── DuckDB ──────────────────────────────────────────────────────────────
    elif t == "duckdb":
        fp = db_config.get("file_path", ":memory:")
        return create_engine(f"duckdb:///{fp}", poolclass=NullPool)

    # ── Snowflake ───────────────────────────────────────────────────────────
    elif t == "snowflake":
        account   = db_config.get("account", "")
        warehouse = db_config.get("warehouse", "")
        schema    = db_config.get("schema", "PUBLIC")
        url = URL.create("snowflake",
                         username=username, password=password,
                         host=f"{account}.snowflakecomputing.com",
                         database=database,
                         query={"warehouse": warehouse, "schema": schema})

    # ── BigQuery ────────────────────────────────────────────────────────────
    elif t == "bigquery":
        project   = db_config.get("project", database)
        creds_env = db_config.get("credentials_env", "")
        if creds_env and os.getenv(creds_env):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv(creds_env)
        return create_engine(f"bigquery://{project}", poolclass=NullPool)

    # ── Oracle ──────────────────────────────────────────────────────────────
    # Uses python-oracledb in "thin" mode — no Oracle Instant Client needed!
    # Install with: pip install oracledb sqlalchemy-oracledb
    elif t == "oracle":
        service = db_config.get("service_name", database or "XEPDB1")
        url = URL.create("oracle+oracledb",
                         username=username, password=password,
                         host=host, port=int(port or 1521),
                         query={"service_name": service})

    # ── Databricks ──────────────────────────────────────────────────────────
    elif t == "databricks":
        token     = _env(db_config, "token_env")
        http_path = db_config.get("http_path", "")
        catalog   = db_config.get("catalog", "")
        conn_str  = (f"databricks://token:{token}@{host}?"
                     f"http_path={quote_plus(http_path)}"
                     f"&catalog={catalog}&schema={database}")
        return create_engine(conn_str, poolclass=NullPool)

    # ── Redshift ────────────────────────────────────────────────────────────
    elif t == "redshift":
        url = URL.create("redshift+redshift_connector",
                         username=username, password=password,
                         host=host, port=int(port or 5439), database=database)

    else:
        raise ValueError(f"Unsupported database type: '{t}' for '{db_key}'")

    return create_engine(url, poolclass=NullPool)


# ─────────────────────────────────────────────────────────────────────────────
# Connection test
# ─────────────────────────────────────────────────────────────────────────────

def test_connection(db_key: str, db_config: Dict) -> Tuple[bool, str, float]:
    """Ping a database. Returns (success, message, latency_seconds)."""
    # Oracle requires FROM DUAL for standalone SELECTs
    ping_sql = {
        "oracle": "SELECT 1 FROM DUAL",
    }
    db_type = db_config.get("type", "")
    query = ping_sql.get(db_type, "SELECT 1")

    start = time.perf_counter()
    try:
        engine = build_engine(db_key, db_config)
        with engine.connect() as conn:
            conn.execute(text(query))
        latency = time.perf_counter() - start
        return True, "Connected successfully", round(latency, 3)
    except Exception as e:
        latency = time.perf_counter() - start
        return False, str(e), round(latency, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Schema discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_schema(db_key: str, db_config: Dict) -> Dict:
    """
    Auto-discover tables, columns (with types + PK flags),
    views, and stored procedures from a live database connection.
    """
    result = {
        "db_key":        db_key,
        "name":          db_config.get("name", db_key),
        "type":          db_config.get("type", "unknown"),
        "domain":        db_config.get("domain", ""),
        "description":   db_config.get("description", ""),
        "tables":        {},
        "views":         [],
        "procedures":    [],
        "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "error":         None,
    }

    try:
        engine      = build_engine(db_key, db_config)
        inspector   = sa_inspect(engine)
        db_type     = db_config["type"]
        schema_name = db_config.get("schema", None)

        # ── Tables + columns + keys ─────────────────────────────────────────
        try:
            tables = inspector.get_table_names(schema=schema_name)
            for table in tables:
                cols = inspector.get_columns(table, schema=schema_name)
                pk   = inspector.get_pk_constraint(table, schema=schema_name)
                fks  = inspector.get_foreign_keys(table, schema=schema_name)
                pk_cols = set(pk.get("constrained_columns") or [])

                result["tables"][table] = {
                    "columns": [
                        {
                            "name":        c["name"],
                            "type":        str(c["type"]),
                            "nullable":    c.get("nullable", True),
                            "primary_key": c["name"] in pk_cols,
                        }
                        for c in cols
                    ],
                    "foreign_keys": [
                        {
                            "columns":    fk["constrained_columns"],
                            "references": f"{fk['referred_table']}.{fk['referred_columns']}",
                        }
                        for fk in fks
                    ],
                    "row_count": None,  # filled in optionally below
                }
        except Exception as e:
            result["error"] = f"Table discovery error: {e}"

        # ── Views ───────────────────────────────────────────────────────────
        try:
            result["views"] = inspector.get_view_names(schema=schema_name)
        except Exception:
            pass

        # ── Stored procedures (dialect-specific) ───────────────────────────
        try:
            with engine.connect() as conn:
                if db_type == "mssql":
                    rows = conn.execute(
                        text("SELECT name FROM sys.procedures ORDER BY name")
                    ).fetchall()
                    result["procedures"] = [r[0] for r in rows]

                elif db_type == "postgresql":
                    rows = conn.execute(text(
                        "SELECT routine_name FROM information_schema.routines "
                        "WHERE routine_type = 'FUNCTION' "
                        "  AND routine_schema NOT IN ('pg_catalog', 'information_schema') "
                        "ORDER BY routine_name"
                    )).fetchall()
                    result["procedures"] = [r[0] for r in rows]

                elif db_type == "mysql":
                    rows = conn.execute(
                        text("SHOW PROCEDURE STATUS WHERE Db = DATABASE()")
                    ).fetchall()
                    result["procedures"] = [r[1] for r in rows]

                elif db_type == "snowflake":
                    rows = conn.execute(
                        text("SHOW PROCEDURES")
                    ).fetchall()
                    result["procedures"] = [r[1] for r in rows] if rows else []

        except Exception:
            pass  # procedures are optional

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Schema cache
# ─────────────────────────────────────────────────────────────────────────────

def load_schema_cache() -> Dict:
    if SCHEMA_CACHE_PATH.exists():
        with open(SCHEMA_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_schema_cache(cache: Dict):
    with open(SCHEMA_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, default=str)

def refresh_schema(db_key: str, db_config: Dict) -> Dict:
    """Discover and cache schema for a single database. Returns the schema."""
    schema = discover_schema(db_key, db_config)
    cache  = load_schema_cache()
    cache[db_key] = schema
    save_schema_cache(cache)
    return schema

def refresh_all_schemas():
    """Discover and cache schemas for all enabled databases."""
    results = {}
    for db_key, db_config in get_enabled_databases().items():
        results[db_key] = refresh_schema(db_key, db_config)
    return results

def get_schema_for_llm(db_keys: List[str] = None) -> str:
    """
    Build a compact, LLM-friendly schema description from the cache.
    If db_keys is None, include all cached databases.
    Marks primary key columns with *.
    """
    cache = load_schema_cache()
    if db_keys:
        cache = {k: v for k, v in cache.items() if k in db_keys}

    if not cache:
        return "No schema discovered yet. Visit the Connection Manager to scrape schemas."

    parts = []
    for db_key, schema in cache.items():
        if schema.get("error") and not schema.get("tables"):
            parts.append(f"[{db_key.upper()}] ERROR: {schema['error']}")
            continue

        db_type   = schema.get("type", "?").upper()
        db_name   = schema.get("name", db_key)
        domain    = schema.get("domain", "")
        domain_str = f" | Domain: {domain}" if domain else ""
        lines = [f"[{db_key.upper()} | {db_name} | {db_type}{domain_str}]"]

        for table, info in schema.get("tables", {}).items():
            col_parts = []
            for c in info["columns"]:
                flag = "*" if c["primary_key"] else ""
                col_parts.append(f"{c['name']}{flag} ({c['type']})")
            lines.append(f"  Table {table}: {', '.join(col_parts)}")

            for fk in info.get("foreign_keys", []):
                lines.append(f"    FK: {fk['columns']} → {fk['references']}")

        if schema.get("views"):
            lines.append(f"  Views: {', '.join(schema['views'])}")
        if schema.get("procedures"):
            procs = schema["procedures"][:15]
            suffix = f" (+{len(schema['procedures'])-15} more)" if len(schema['procedures']) > 15 else ""
            lines.append(f"  Procedures: {', '.join(procs)}{suffix}")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Row limit injection
# ─────────────────────────────────────────────────────────────────────────────

def _inject_row_limit(sql: str, db_type: str, max_rows: int) -> tuple:
    """
    Inject a row limit into a SQL query if one isn't already present.

    Why this matters: without a limit, a query like "SELECT * FROM Claims"
    could return hundreds of thousands of rows, crash the browser, and saturate
    memory. This function adds a safe cap before the query ever hits the DB.

    Strategy by database type:
      - mssql   → SELECT TOP N  (injected after the SELECT keyword)
      - oracle  → wraps in subquery with ROWNUM <= N
      - others  → appends LIMIT N at the end (PostgreSQL, MySQL, SQLite, etc.)

    Returns: (modified_sql, was_limited: bool)
      was_limited=True means we added the limit — the UI can warn the user.
      was_limited=False means the query already had a limit — left untouched.
    """
    stripped = sql.strip().rstrip(";")
    upper    = stripped.upper()

    # ── Already has a row cap — leave it alone ──────────────────────────────
    already_limited = (
        bool(re.search(r"\bTOP\s+\d+",         upper)) or   # SQL Server TOP N
        bool(re.search(r"\bLIMIT\s+\d+",        upper)) or   # MySQL / Postgres LIMIT N
        bool(re.search(r"\bFETCH\s+FIRST\b",    upper)) or   # ANSI FETCH FIRST N ROWS
        bool(re.search(r"\bROWNUM\s*<=?\s*\d+", upper))      # Oracle ROWNUM
    )
    if already_limited:
        return sql, False

    # ── Inject based on database dialect ────────────────────────────────────
    if db_type == "mssql":
        # Inject TOP N right after the first SELECT keyword.
        # count=1 means only the outermost (or CTE's inner) SELECT is touched.
        # The negative lookahead (?!\s+TOP\b) prevents double-injection.
        modified = re.sub(
            r"(?i)\bSELECT\b(?!\s+TOP\b)",
            f"SELECT TOP {max_rows}",
            stripped,
            count=1,
        )

    elif db_type == "oracle":
        # Oracle doesn't support TOP — wrap the whole query in a subquery
        # and filter with ROWNUM. "AS __r" is the alias for the subquery.
        modified = f"SELECT * FROM ({stripped}) AS __r WHERE ROWNUM <= {max_rows}"

    else:
        # PostgreSQL, MySQL, SQLite, DuckDB, Snowflake, BigQuery, Redshift
        modified = stripped + f"\nLIMIT {max_rows}"

    return modified, True


# ─────────────────────────────────────────────────────────────────────────────
# Query execution
# ─────────────────────────────────────────────────────────────────────────────

def execute_query(db_key: str, db_config: Dict, sql: str, max_rows: int = 500) -> Dict[str, Any]:
    """
    Execute a SELECT query on a registered database.

    max_rows (default 500): hard cap injected into the SQL before execution.
    Set to 0 to disable the cap entirely (use with caution on large tables).

    Returns:
      {"success": True,  "data": DataFrame, "latency": float, "was_limited": bool}
      {"success": False, "error": str,      "latency": float}
    """
    if not sql or not sql.strip():
        return {"success": False, "error": "Empty query.", "latency": 0}

    # ── Safety gate — only allow read-only operations ────────────────────────
    first_word = sql.strip().lstrip("-").strip().split()[0].upper()
    if first_word not in ("SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"):
        return {"success": False, "error": "Only SELECT/WITH queries are permitted.", "latency": 0}

    # ── Inject row limit (unless disabled or already present) ────────────────
    db_type = db_config.get("type", "")
    if max_rows and max_rows > 0:
        sql, was_limited = _inject_row_limit(sql, db_type, max_rows)
    else:
        was_limited = False

    start = time.perf_counter()
    try:
        engine = build_engine(db_key, db_config)
        with engine.connect() as conn:
            df = pd.read_sql_query(text(sql), conn)
        return {
            "success":     True,
            "data":        df,
            "latency":     round(time.perf_counter() - start, 4),
            "was_limited": was_limited,   # True if we injected a TOP/LIMIT cap
            "max_rows":    max_rows,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "latency": round(time.perf_counter() - start, 4)}


# ─────────────────────────────────────────────────────────────────────────────
# Domain → DB key resolver (used by the BI dashboard routing)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_domain(domain: str) -> Optional[Tuple[str, Dict]]:
    """
    Given a domain string (e.g. 'HR', 'CLAIMS'), return (db_key, db_config)
    from the registry, or None if not found.
    """
    domain_map = get_domain_map()
    db_key = domain_map.get(domain.upper())
    if db_key:
        return db_key, get_enabled_databases()[db_key]
    return None
