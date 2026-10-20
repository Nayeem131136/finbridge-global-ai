"""SQLite access and a tiny migration runner (applies backend/migrations/*.sql in order, once each).

SQLite keeps local setup to zero. The schema is plain SQL, so a PostgreSQL deployment needs only type tweaks
(AUTOINCREMENT -> SERIAL, datetime('now') -> now()). PostgreSQL is NOT implemented in this prototype.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_path: str | None = None


def db_path() -> str:
    return os.getenv("FINBRIDGE_DB", str(ROOT / "data" / "finbridge.db"))


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open (or reopen) the database and apply pending migrations."""
    global _conn, _path
    with _lock:
        path = path or db_path()
        if _conn is not None and _path == path:
            return _conn
        if _conn is not None:
            _conn.close()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL") if path != ":memory:" else None
        _path = path
        migrate(_conn)
        return _conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))")
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name in done:
            continue
        conn.execute("BEGIN")
        try:
            for stmt in _split(f.read_text(encoding="utf-8")):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations(name) VALUES (?)", (f.name,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        applied.append(f.name)
    return applied


def _split(sql: str) -> list[str]:
    out, buf = [], ""
    for line in sql.splitlines():
        buf += line + "\n"
        if sqlite3.complete_statement(buf):          # understands ';' inside comments and strings
            out.append(buf.strip())
            buf = ""
    return [x for x in out if x]


@contextmanager
def tx():
    """Serialised transaction: commit on success, roll back on any error."""
    conn = connect()
    with _lock:
        conn.execute("BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def run(sql: str, args: tuple = ()) -> sqlite3.Cursor:
    """Single auto-committed statement, serialised with every other database call."""
    conn = connect()
    with _lock:
        return conn.execute(sql, args)


def q(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    conn = connect()
    with _lock:
        return conn.execute(sql, args).fetchall()


def q1(sql: str, args: tuple = ()):
    rows = q(sql, args)
    return rows[0] if rows else None
