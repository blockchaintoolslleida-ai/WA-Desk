"""
Database client initialization — local SQLite + JWT (replaces Supabase)
"""
from local_db import LocalDB, init_db, DB_PATH
import os

# Initialize DB schema and seed data on first run
init_db()

# Single LocalDB instance used by all routers (replaces both supabase and supabase_admin)
_local_db = LocalDB()


def get_supabase():
    """Get the database client for regular operations (auth login/signout)."""
    return _local_db


def get_supabase_admin():
    """Get the admin database client for server-side operations (all CRUD)."""
    return _local_db
