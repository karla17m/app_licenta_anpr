import sqlite3
from flask import g

DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            DATABASE,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None  # For autocommit mode
        )
        g.db.row_factory = sqlite3.Row
        # Enable foreign key constraints
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
