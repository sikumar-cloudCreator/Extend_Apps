#!/usr/bin/env python3
"""
db.py — the small shared database for the Extend LLM agent (SQLite).

Holds the two learning surfaces so they persist and compound across the whole team:
  • lessons  — distilled rules (knowledge_base)
  • feedback — accepted/corrected examples (feedback_store)

SQLite = one file, no server; perfect for running the Slack bot from Cursor. To share across
machines/replicas later, point EXTEND_DB_PATH at a networked file or swap connect() for Postgres
(same two tables). Path via EXTEND_DB_PATH (default knowledge/extend.db).
"""
import os, sqlite3

DB_PATH = os.path.expanduser(os.environ.get(
    "EXTEND_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "extend.db")))


def connect():
    """Return a connection with the schema ensured. Reads the current DB_PATH each call (tests override it)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS lessons(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, scope TEXT, rule TEXT, why TEXT, source TEXT,
        UNIQUE(scope, rule))""")
    c.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, request TEXT, output TEXT,
        accepted INTEGER, verdict TEXT, comment TEXT, meta TEXT)""")
    return c
