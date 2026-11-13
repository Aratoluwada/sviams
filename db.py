"""SQLite access. Plain queries only: the rules live in logic.py."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tags (
    uid TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    plate TEXT,
    assigned_at TEXT
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    plate_read TEXT,
    uid TEXT,
    result TEXT NOT NULL,
    overridden INTEGER DEFAULT 0,
    notes TEXT,
    image_path TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_plate ON transactions(plate_read);
CREATE INDEX IF NOT EXISTS idx_tx_uid ON transactions(uid);
CREATE INDEX IF NOT EXISTS idx_tx_time ON transactions(timestamp);
"""


def now_iso():
    """ISO 8601 time in the one zone set in config."""
    tz = timezone(timedelta(hours=config.UTC_OFFSET_HOURS))
    return datetime.now(tz).isoformat(timespec="seconds")


def connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction():
    """One database transaction: commits on success, rolls back on any error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _use(conn):
    """Use the caller's connection (part of a bigger transaction) or open our own."""
    if conn is not None:
        yield conn
    else:
        with transaction() as own:
            yield own


def init_db():
    with transaction() as conn:
        conn.executescript(SCHEMA)


# ---- tags -----------------------------------------------------------------

def get_tag(uid, conn=None):
    with _use(conn) as c:
        row = c.execute("SELECT * FROM tags WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else None


def list_tags(conn=None):
    with _use(conn) as c:
        return [dict(r) for r in c.execute("SELECT * FROM tags ORDER BY uid")]


def add_tag(uid, conn=None):
    """Register a new card as available. Returns False if it already exists."""
    with _use(conn) as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO tags (uid, status) VALUES (?, 'available')", (uid,)
        )
        return cur.rowcount == 1


def set_tag(uid, status, plate=None, conn=None):
    """Change a tag. The plate and time are kept only while status is 'assigned'."""
    assigned = status == "assigned"
    with _use(conn) as c:
        cur = c.execute(
            "UPDATE tags SET status = ?, plate = ?, assigned_at = ? WHERE uid = ?",
            (status, plate if assigned else None, now_iso() if assigned else None, uid),
        )
        if cur.rowcount != 1:
            raise LookupError(f"Unknown tag {uid}")


# ---- transactions ---------------------------------------------------------

def log_transaction(type_, plate_read, uid, result, overridden=0, notes=None,
                    image_path=None, conn=None):
    with _use(conn) as c:
        cur = c.execute(
            "INSERT INTO transactions "
            "(timestamp, type, plate_read, uid, result, overridden, notes, image_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now_iso(), type_, plate_read, uid, result, int(overridden), notes, image_path),
        )
        return cur.lastrowid


def get_transaction(tx_id, conn=None):
    with _use(conn) as c:
        row = c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None


def mark_overridden(tx_id, note, conn=None):
    with _use(conn) as c:
        cur = c.execute(
            "UPDATE transactions SET overridden = 1, notes = ? WHERE id = ?", (note, tx_id)
        )
        if cur.rowcount != 1:
            raise LookupError(f"Unknown transaction {tx_id}")


def _like(text):
    """Escape LIKE wildcards so searches match the text literally."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_transactions(date_from=None, date_to=None, plate=None, uid=None,
                      result=None, limit=500, conn=None):
    # Only fixed SQL fragments are joined below; every value goes in as a ? parameter.
    clauses, params = [], []
    if date_from:
        clauses.append("substr(timestamp, 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("substr(timestamp, 1, 10) <= ?")
        params.append(date_to)
    if plate:
        clauses.append("plate_read LIKE ? ESCAPE '\\'")
        params.append(_like(plate.upper()))
    if uid:
        clauses.append("uid LIKE ? ESCAPE '\\'")
        params.append(_like(uid.upper()))
    if result:
        clauses.append("result = ?")
        params.append(result)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with _use(conn) as c:
        rows = c.execute(
            f"SELECT * FROM transactions {where} ORDER BY id DESC LIMIT ?", params
        )
        return [dict(r) for r in rows]


# ---- admins ---------------------------------------------------------------

def add_admin(username, password_hash, conn=None):
    """Create an admin, or replace the password if the username exists."""
    with _use(conn) as c:
        c.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash",
            (username, password_hash),
        )


def get_admin(username, conn=None):
    with _use(conn) as c:
        row = c.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
