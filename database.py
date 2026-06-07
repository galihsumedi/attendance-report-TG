from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
from flask import Flask, g


class DbWrapper:
    """Thin adapter presenting a sqlite3-like interface over a psycopg2 connection.

    Converts ? placeholders to %s so existing query strings work unchanged.
    Rows returned by execute() are RealDictRow -- subscriptable by column name.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db() -> DbWrapper:
    if "db" not in g:
        conn = psycopg2.connect(
            os.environ["DATABASE_URL"],
            options="-c search_path=attendance",
            sslmode="require",
        )
        conn.autocommit = False
        g.db = DbWrapper(conn)
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    app.teardown_appcontext(close_db)
