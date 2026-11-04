"""Database access for ShadowFind (SQLite, parameterised statements only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    department    TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK (type IN ('lost', 'found')),
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    place       TEXT    NOT NULL DEFAULT '',
    seen_on     TEXT    NOT NULL DEFAULT '',
    photo       TEXT    NOT NULL DEFAULT '',
    overlay     TEXT    NOT NULL DEFAULT '',
    descriptor  BLOB,
    shadow_iou  REAL    NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lost_item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    found_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    score         REAL    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (lost_item_id, found_item_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    sender_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status      TEXT    NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'rejected', 'returned')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_type   ON items(type);
CREATE INDEX IF NOT EXISTS idx_items_student ON items(student_id);
CREATE INDEX IF NOT EXISTS idx_claims_recv   ON claims(receiver_id);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path) -> None:
    """Create the schema if it is not there yet."""
    with connect(path) as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# students
# ---------------------------------------------------------------------------
def create_student(conn, name, email, password, department) -> int:
    cur = conn.execute(
        "INSERT INTO students (name, email, password_hash, department) VALUES (?, ?, ?, ?)",
        (name.strip(), email.strip().lower(), generate_password_hash(password), department.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def find_student_by_email(conn, email):
    return conn.execute("SELECT * FROM students WHERE email = ?", (email.strip().lower(),)).fetchone()


def verify_student(conn, email, password):
    row = find_student_by_email(conn, email)
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def get_student(conn, student_id):
    return conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------
def create_item(conn, *, student_id, title, type_, category, description,
                place, seen_on, photo, overlay, descriptor, shadow_iou) -> int:
    import numpy as np

    blob = descriptor.astype(np.float32).tobytes() if descriptor is not None else None
    cur = conn.execute(
        """INSERT INTO items
           (student_id, title, type, category, description, place, seen_on,
            photo, overlay, descriptor, shadow_iou)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, title.strip(), type_, category, description.strip(),
         place.strip(), seen_on, photo, overlay, blob, float(shadow_iou)),
    )
    conn.commit()
    return int(cur.lastrowid)


def descriptor_of(row):
    import numpy as np

    blob = row["descriptor"]
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.float32).copy()


def list_items(conn, *, exclude_student=None, type_=None, category=None, limit=100):
    sql = ["SELECT i.*, s.name AS student_name, s.department FROM items i",
           "JOIN students s ON s.id = i.student_id WHERE 1=1"]
    args = []
    if exclude_student is not None:
        sql.append("AND i.student_id != ?")
        args.append(exclude_student)
    if type_:
        sql.append("AND i.type = ?")
        args.append(type_)
    if category:
        sql.append("AND i.category = ?")
        args.append(category)
    sql.append("ORDER BY i.created_at DESC, i.id DESC LIMIT ?")
    args.append(int(limit))
    return conn.execute(" ".join(sql), args).fetchall()


def get_item(conn, item_id):
    return conn.execute(
        """SELECT i.*, s.name AS student_name, s.department, s.email AS student_email
           FROM items i JOIN students s ON s.id = i.student_id WHERE i.id = ?""",
        (item_id,),
    ).fetchone()


def candidates_for(conn, item_row):
    """Found/lost items of the opposite type in the same category, with descriptors."""
    opposite = "found" if item_row["type"] == "lost" else "lost"
    rows = conn.execute(
        """SELECT i.*, s.name AS student_name, s.department
           FROM items i JOIN students s ON s.id = i.student_id
           WHERE i.type = ? AND i.descriptor IS NOT NULL""",
        (opposite,),
    ).fetchall()
    same = [r for r in rows if r["category"] == item_row["category"]]
    return same or list(rows)


def save_match(conn, lost_id, found_id, score):
    conn.execute(
        """INSERT INTO matches (lost_item_id, found_item_id, score)
           VALUES (?, ?, ?)
           ON CONFLICT(lost_item_id, found_item_id)
           DO UPDATE SET score = excluded.score""",
        (lost_id, found_id, float(score)),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM matches WHERE lost_item_id = ? AND found_item_id = ?",
        (lost_id, found_id),
    ).fetchone()["id"]


# ---------------------------------------------------------------------------
# claims
# ---------------------------------------------------------------------------
def create_claim(conn, match_id, sender_id, receiver_id):
    existing = conn.execute(
        "SELECT id FROM claims WHERE match_id = ? AND sender_id = ? AND status IN ('pending','accepted')",
        (match_id, sender_id),
    ).fetchone()
    if existing:
        return int(existing["id"]), False
    cur = conn.execute(
        "INSERT INTO claims (match_id, sender_id, receiver_id) VALUES (?, ?, ?)",
        (match_id, sender_id, receiver_id),
    )
    conn.commit()
    return int(cur.lastrowid), True


def incoming_claims(conn, student_id):
    return conn.execute(
        """SELECT c.*, m.score,
                  li.title AS lost_title, fi.title AS found_title,
                  fi.id AS found_id, li.id AS lost_id,
                  s.name AS sender_name, s.department AS sender_dept
           FROM claims c
           JOIN matches m ON m.id = c.match_id
           JOIN items  li ON li.id = m.lost_item_id
           JOIN items  fi ON fi.id = m.found_item_id
           JOIN students s ON s.id = c.sender_id
           WHERE c.receiver_id = ?
           ORDER BY c.created_at DESC, c.id DESC""",
        (student_id,),
    ).fetchall()


def sent_claims(conn, student_id):
    return conn.execute(
        """SELECT c.*, m.score,
                  li.title AS lost_title, fi.title AS found_title,
                  r.name AS receiver_name, r.department AS receiver_dept
           FROM claims c
           JOIN matches m ON m.id = c.match_id
           JOIN items  li ON li.id = m.lost_item_id
           JOIN items  fi ON fi.id = m.found_item_id
           JOIN students r ON r.id = c.receiver_id
           WHERE c.sender_id = ?
           ORDER BY c.created_at DESC, c.id DESC""",
        (student_id,),
    ).fetchall()


def get_claim(conn, claim_id):
    return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()


def set_claim_status(conn, claim_id, status):
    conn.execute("UPDATE claims SET status = ? WHERE id = ?", (status, claim_id))
    # returning the item closes every other open claim on the same match
    if status == "accepted":
        conn.execute(
            "UPDATE claims SET status = 'rejected' WHERE match_id = "
            "(SELECT match_id FROM claims WHERE id = ?) AND id != ? AND status = 'pending'",
            (claim_id, claim_id),
        )
    conn.commit()


def stats(conn):
    def one(sql):
        row = conn.execute(sql).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    return {
        "lost": one("SELECT COUNT(*) FROM items WHERE type='lost'"),
        "found": one("SELECT COUNT(*) FROM items WHERE type='found'"),
        "returned": one("SELECT COUNT(*) FROM claims WHERE status='returned'"),
        "matched": one("SELECT COUNT(*) FROM items WHERE shadow_iou > 0"),
    }
