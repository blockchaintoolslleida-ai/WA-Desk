"""
LocalDB — Drop-in replacement for Supabase Client using SQLite + JWT

Mimics the supabase-py API surface so all existing routers work unchanged:
  client.table('x').select('*').eq('id', val).single().execute()
  client.auth.sign_in_with_password({email, password})
  client.storage.from_('media').upload(path, bytes, file_options)
"""
import sqlite3
import uuid
import json
import os
import re
import hashlib
import hmac
import mimetypes
from datetime import datetime, timezone, timedelta
from pathlib import Path
from functools import lru_cache

import jwt as pyjwt

DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "local.db"
MEDIA_DIR = DB_DIR / "media_files"

JWT_SECRET = os.environ.get("JWT_SECRET", "local-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))

# JSONB columns that need auto-parsing from TEXT storage
JSON_COLUMNS = {'old_value', 'new_value', 'payload_json'}

# Columns known to be booleans (stored as INTEGER 0/1 in SQLite)
BOOL_COLUMNS = {'is_active', 'needs_classification', 'unread_count', 'email_confirm'}


# ═══════════════════════════════════════════════════════════════════
# Password Hashing (PBKDF2-HMAC-SHA256 — stdlib only)
# ═══════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with 100k iterations. Returns `salt_hex$hash_hex`."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + '$' + key.hex()


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored `salt$hash` string."""
    try:
        salt_hex, key_hex = stored.split('$')
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hmac.compare_digest(key.hex(), key_hex)


# ═══════════════════════════════════════════════════════════════════
# JWT Helpers
# ═══════════════════════════════════════════════════════════════════

def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str):
    """Returns decoded payload or raises on invalid/expired token."""
    return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ═══════════════════════════════════════════════════════════════════
# Response (mimics supabase-py APIResponse)
# ═══════════════════════════════════════════════════════════════════

class Response:
    """Fake Supabase API response with .data and .count attributes."""
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


# ═══════════════════════════════════════════════════════════════════
# QueryBuilder (mimics supabase-py sync QueryBuilder)
# ═══════════════════════════════════════════════════════════════════

class QueryBuilder:
    """Chainable query builder that mimics the Supabase Python client."""

    def __init__(self, table_name: str, db_path: str):
        self._table = table_name
        self._db_path = db_path
        self._select_cols = '*'
        self._filters = []          # list of (op, col, val)
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._single_mode = False
        self._maybe_single = False
        self._count_exact = False
        self._nested_joins = []     # [(table_name, [col1, col2, ...]), ...]
        self._operation = None
        self._insert_data = None
        self._update_data = None
        self._is_upsert = False

    # ── select ──────────────────────────────────────────────────

    def select(self, cols: str, **kwargs):
        self._operation = 'select'
        self._select_cols = cols
        if kwargs.get('count') == 'exact':
            self._count_exact = True
        # Parse nested joins: '*, contacts(id, name, phone)'
        nested_pattern = r'(\w+)\(([^)]+)\)'
        for match in re.finditer(nested_pattern, cols):
            self._nested_joins.append(
                (match.group(1), [c.strip() for c in match.group(2).split(',')])
            )
        return self

    # ── filter chain methods ────────────────────────────────────

    def eq(self, col: str, val):
        self._filters.append(('eq', col, val))
        return self

    def neq(self, col: str, val):
        self._filters.append(('neq', col, val))
        return self

    def in_(self, col: str, vals):
        if isinstance(vals, (list, tuple)):
            self._filters.append(('in', col, list(vals)))
        else:
            self._filters.append(('eq', col, vals))
        return self

    def is_(self, col: str, val):
        self._filters.append(('is', col, val))
        return self

    def gte(self, col: str, val):
        self._filters.append(('gte', col, val))
        return self

    def order(self, col: str, desc: bool = False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    def single(self):
        self._single_mode = True
        self._maybe_single = False
        return self

    def maybe_single(self):
        self._maybe_single = True
        self._single_mode = False
        return self

    # ── mutation methods ────────────────────────────────────────

    def insert(self, data):
        self._operation = 'insert'
        self._insert_data = data if isinstance(data, list) else [data]
        return self

    def upsert(self, data):
        self._operation = 'insert'
        self._insert_data = data if isinstance(data, list) else [data]
        self._is_upsert = True
        return self

    def update(self, data: dict):
        self._operation = 'update'
        self._update_data = data
        return self

    def delete(self):
        self._operation = 'delete'
        return self

    # ── internal helpers ────────────────────────────────────────

    def _get_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _get_table_columns(self, conn, table: str) -> set:
        try:
            rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            return {r['name'] for r in rows}
        except Exception:
            return set()

    def _build_where(self):
        clauses = []
        params = []
        for op, col, val in self._filters:
            if op == 'eq':
                clauses.append(f'"{col}" = ?')
                params.append(val)
            elif op == 'neq':
                clauses.append(f'"{col}" != ?')
                params.append(val)
            elif op == 'in':
                placeholders = ','.join('?' for _ in val)
                clauses.append(f'"{col}" IN ({placeholders})')
                params.extend(val)
            elif op == 'is':
                if val == 'null' or val is None:
                    clauses.append(f'"{col}" IS NULL')
                else:
                    clauses.append(f'"{col}" IS ?')
                    params.append(val)
            elif op == 'gte':
                clauses.append(f'"{col}" >= ?')
                params.append(val)
        where = ' AND '.join(clauses) if clauses else '1=1'
        return where, params

    def _clean_select_cols(self):
        """Remove nested join patterns from select columns for SQL."""
        return re.sub(r'\s*\w+\([^)]+\)', '', self._select_cols).strip(', ').strip()

    def _resolve_nested_joins(self, rows: list, conn) -> list:
        """For each row, fetch nested relations like contacts(id, name)."""
        if not self._nested_joins:
            return rows

        for row in rows:
            for nested_table, nested_cols in self._nested_joins:
                # Map table name to FK column: contacts -> contact_id, cases -> case_id
                singular = nested_table[:-1] if nested_table.endswith('s') else nested_table
                fk_col = f"{singular}_id"

                # Special case: profiles lookup via assigned_agent_id / created_by / author_id
                fk_val = row.get(fk_col)
                if fk_val:
                    try:
                        cols_sql = ', '.join(f'"{c}"' for c in nested_cols)
                        nested_row = conn.execute(
                            f'SELECT {cols_sql} FROM "{nested_table}" WHERE "id" = ?',
                            (fk_val,)
                        ).fetchone()
                        if nested_row:
                            # Convert to dict with proper types
                            nested_dict = {}
                            for c in nested_cols:
                                nested_dict[c] = nested_row[c]
                            row[nested_table] = nested_dict
                        else:
                            row[nested_table] = None
                    except Exception:
                        row[nested_table] = None
                else:
                    row[nested_table] = None
        return rows

    def _parse_row_values(self, row_dict: dict) -> dict:
        """Parse JSON columns and normalize types."""
        for col in JSON_COLUMNS:
            if col in row_dict and isinstance(row_dict[col], str):
                try:
                    row_dict[col] = json.loads(row_dict[col])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row_dict

    def _serialize_json_columns(self, data: dict) -> dict:
        """Convert dict/list values in JSONB columns to JSON strings for storage."""
        result = {}
        for k, v in data.items():
            if k in JSON_COLUMNS and isinstance(v, (dict, list)):
                result[k] = json.dumps(v)
            else:
                result[k] = v
        return result

    # ── execute ─────────────────────────────────────────────────

    def execute(self) -> Response:
        conn = self._get_conn()
        try:
            return self._execute_inner(conn)
        finally:
            conn.close()

    def _execute_inner(self, conn) -> Response:
        where_clause, params = self._build_where()

        # ── SELECT ──────────────────────────────────────────────
        if self._operation == 'select':
            clean_cols = self._clean_select_cols()
            if not clean_cols:
                clean_cols = '*'
            sql = f'SELECT {clean_cols} FROM "{self._table}" WHERE {where_clause}'
            if self._order_col:
                direction = 'DESC' if self._order_desc else 'ASC'
                sql += f' ORDER BY "{self._order_col}" {direction}'
            if self._limit_val:
                sql += f' LIMIT {self._limit_val}'

            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as e:
                if 'no such table' in str(e).lower():
                    return Response(None if (self._single_mode or self._maybe_single) else [], 0)
                raise

            data = [dict(r) for r in rows]
            data = [self._parse_row_values(d) for d in data]
            data = self._resolve_nested_joins(data, conn)

            count = None
            if self._count_exact:
                count_sql = f'SELECT COUNT(*) as cnt FROM "{self._table}" WHERE {where_clause}'
                try:
                    cnt_row = conn.execute(count_sql, params).fetchone()
                    count = cnt_row['cnt'] if cnt_row else 0
                except Exception:
                    count = len(data)

            if self._single_mode:
                return Response(data[0] if data else None, count)
            if self._maybe_single:
                return Response(data[0] if data else None, count)
            return Response(data, count)

        # ── INSERT ──────────────────────────────────────────────
        elif self._operation == 'insert':
            known_cols = self._get_table_columns(conn, self._table)
            inserted = []

            for item in self._insert_data:
                item = self._serialize_json_columns(item)
                filtered = {k: v for k, v in item.items() if k in known_cols}
                if not filtered:
                    continue

                cols = ', '.join(f'"{k}"' for k in filtered.keys())
                phs = ', '.join('?' for _ in filtered)
                vals = list(filtered.values())

                try:
                    if self._is_upsert:
                        sql = f'INSERT OR REPLACE INTO "{self._table}" ({cols}) VALUES ({phs})'
                    else:
                        sql = f'INSERT INTO "{self._table}" ({cols}) VALUES ({phs})'
                    conn.execute(sql, vals)
                except sqlite3.IntegrityError:
                    # Unique constraint violation — silently skip (duplicate agent, etc.)
                    pass
                except sqlite3.OperationalError as e:
                    if 'no such column' in str(e).lower():
                        # Two-attempt pattern: retry with only known columns
                        known = {k: v for k, v in filtered.items() if k in known_cols}
                        if known:
                            cols2 = ', '.join(f'"{k}"' for k in known.keys())
                            phs2 = ', '.join('?' for _ in known)
                            conn.execute(
                                f'INSERT INTO "{self._table}" ({cols2}) VALUES ({phs2})',
                                list(known.values())
                            )
                    else:
                        raise
                inserted.append(filtered)

            conn.commit()
            return Response(self._insert_data, len(inserted))

        # ── UPDATE ──────────────────────────────────────────────
        elif self._operation == 'update':
            known_cols = self._get_table_columns(conn, self._table)
            update_data = self._serialize_json_columns(self._update_data)
            filtered = {k: v for k, v in update_data.items() if k in known_cols}

            if not filtered:
                return Response([])

            set_clause = ', '.join(f'"{k}" = ?' for k in filtered.keys())
            sql = f'UPDATE "{self._table}" SET {set_clause} WHERE {where_clause}'

            try:
                conn.execute(sql, list(filtered.values()) + params)
            except sqlite3.OperationalError as e:
                if 'no such column' in str(e).lower():
                    # Retry with only known columns
                    known = {k: v for k, v in filtered.items() if k in known_cols}
                    if known:
                        sc = ', '.join(f'"{k}" = ?' for k in known.keys())
                        conn.execute(
                            f'UPDATE "{self._table}" SET {sc} WHERE {where_clause}',
                            list(known.values()) + params
                        )
                else:
                    raise

            conn.commit()

            # Return updated rows
            try:
                rows = conn.execute(
                    f'SELECT * FROM "{self._table}" WHERE {where_clause}', params
                ).fetchall()
                return Response([self._parse_row_values(dict(r)) for r in rows])
            except Exception:
                return Response([])

        # ── DELETE ──────────────────────────────────────────────
        elif self._operation == 'delete':
            sql = f'DELETE FROM "{self._table}" WHERE {where_clause}'
            try:
                conn.execute(sql, params)
            except sqlite3.OperationalError as e:
                if 'no such table' in str(e).lower():
                    # Legacy tables may not exist — ignore
                    pass
                else:
                    raise
            conn.commit()
            return Response([])

        return Response([])


# ═══════════════════════════════════════════════════════════════════
# Local Auth (replaces supabase.auth)
# ═══════════════════════════════════════════════════════════════════

class _User:
    """Mimics supabase.User — attributes accessed as .id, .email"""
    def __init__(self, id: str, email: str):
        self.id = id
        self.email = email


class _Session:
    """Mimics supabase.Session"""
    def __init__(self, access_token: str):
        self.access_token = access_token


class _AuthResponse:
    """Mimics supabase AuthResponse with .user and .session"""
    def __init__(self, user=None, session=None):
        self.user = user
        self.session = session


class _AuthAdmin:
    """Mimics supabase.auth.admin namespace."""
    def __init__(self, db_path: str):
        self._db_path = db_path

    def get_user(self, token: str):
        """Validate JWT and return user. Called by all auth helpers in routers."""
        payload = verify_jwt(token)
        return _AuthResponse(user=_User(id=payload['sub'], email=payload['email']))

    def create_user(self, attrs: dict):
        """Create a new auth user. Called by agents.py POST /agents.
        Returns AuthResponse with .user having .id and .email.
        """
        email = attrs.get('email')
        password = attrs.get('password', '')
        uid = str(uuid.uuid4())

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        # Store password hash directly in profiles (the profile is created later by agents.py)
        # Actually, agents.py inserts the profile separately. We just need to return a user ID.
        # But we need the password stored so sign_in_with_password works later.
        # We store it in a separate auth_users table for clean separation.
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS _auth_users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )'''
        )
        try:
            conn.execute(
                'INSERT INTO _auth_users (id, email, password_hash) VALUES (?, ?, ?)',
                (uid, email, hash_password(password))
            )
        except sqlite3.IntegrityError:
            # User already exists — look up existing ID
            row = conn.execute(
                'SELECT id FROM _auth_users WHERE email = ?', (email,)
            ).fetchone()
            if row:
                uid = row['id']
            else:
                raise Exception("User already been registered")

        conn.commit()
        conn.close()
        return _AuthResponse(user=_User(id=uid, email=email))


class _LocalAuth:
    """Mimics supabase.Client.auth interface."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self.admin = _AuthAdmin(db_path)

    def get_user(self, token: str):
        """Validate JWT and return user. Called by all auth helpers in routers.
        Supabase SDK: client.auth.get_user(jwt_token) -> returns user for a JWT.
        """
        payload = verify_jwt(token)
        return _AuthResponse(user=_User(id=payload['sub'], email=payload['email']))

    def sign_in_with_password(self, credentials: dict) -> _AuthResponse:
        """Login with email + password. Returns AuthResponse with .user and .session."""
        email = credentials.get('email', '')
        password = credentials.get('password', '')

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row

        # Look up user in _auth_users or profiles
        row = conn.execute(
            'SELECT id, email, password_hash FROM _auth_users WHERE email = ?',
            (email,)
        ).fetchone()

        if not row:
            # Fallback: check profiles table for pre-seeded users
            row = conn.execute(
                'SELECT id, email, password_hash FROM profiles WHERE email = ? AND is_active = 1',
                (email,)
            ).fetchone()

        conn.close()

        if not row or not verify_password(password, row['password_hash']):
            raise Exception("Invalid login credentials")

        token = create_jwt(row['id'], row['email'])
        return _AuthResponse(
            user=_User(id=row['id'], email=row['email']),
            session=_Session(access_token=token)
        )

    def sign_out(self):
        """No-op for stateless JWT. Called by /api/auth/logout."""
        pass


# ═══════════════════════════════════════════════════════════════════
# Local Storage (replaces supabase.storage)
# ═══════════════════════════════════════════════════════════════════

class _LocalStorageBucket:
    """Mimics supabase.storage bucket interface."""
    def __init__(self, bucket: str, base_dir: Path):
        self._bucket = bucket
        self._base = base_dir / bucket

    def upload(self, path: str, file_bytes: bytes, file_options: dict = None):
        """Store file on local filesystem."""
        full_path = self._base / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_bytes)

    def get_public_url(self, path: str) -> str:
        """Return a local URL for the stored file."""
        base_url = os.environ.get('BASE_URL', 'http://localhost:8000')
        return f"{base_url}/api/media/files/{path}"


class _LocalStorage:
    """Mimics supabase.Client.storage interface."""
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def from_(self, bucket: str) -> _LocalStorageBucket:
        return _LocalStorageBucket(bucket, self._base_dir)


# ═══════════════════════════════════════════════════════════════════
# LocalDB — the main drop-in replacement for supabase.Client
# ═══════════════════════════════════════════════════════════════════

class LocalDB:
    """Drop-in replacement for supabase.Client.

    Usage:
        db = LocalDB()
        db.table('profiles').select('*').eq('id', uid).single().execute()
        db.auth.sign_in_with_password({"email": ..., "password": ...})
        db.storage.from_('media').upload(path, bytes, file_options={...})
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or str(DB_PATH)
        self.auth = _LocalAuth(self._db_path)
        self.storage = _LocalStorage(MEDIA_DIR)

    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(name, self._db_path)

    def rpc(self, *args, **kwargs):
        """Stub for stored procedure calls (not used in this project)."""
        return Response([])


# ═══════════════════════════════════════════════════════════════════
# Schema Definition & Initialization
# ═══════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS _auth_users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    full_name TEXT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'agent',
    phone TEXT,
    username TEXT,
    is_active INTEGER DEFAULT 1,
    tenant_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    notes TEXT,
    source TEXT DEFAULT '',
    tenant_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    service TEXT NOT NULL,
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    token_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL REFERENCES contacts(id),
    status TEXT,
    unread_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    last_message_at TEXT,
    tenant_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    case_id TEXT,
    direction TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    body TEXT,
    media_url TEXT,
    whatsapp_message_id TEXT,
    sender_agent_id TEXT,
    needs_classification INTEGER DEFAULT 0,
    reply_to_id TEXT,
    delivery_status TEXT,
    delivery_error TEXT,
    sent_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'per_atendre',
    assigned_agent_id TEXT,
    priority TEXT DEFAULT 'normal',
    case_type TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS case_events (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    actor_id TEXT,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_views (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    viewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_notes (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS whatsapp_accounts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    business_name TEXT DEFAULT '',
    display_phone_number TEXT DEFAULT '',
    phone_number_id TEXT DEFAULT '',
    whatsapp_business_account_id TEXT DEFAULT '',
    business_manager_id TEXT DEFAULT '',
    meta_app_id TEXT DEFAULT '',
    sender_display_name TEXT DEFAULT '',
    connection_type TEXT DEFAULT 'meta',
    openwa_server_url TEXT DEFAULT '',
    openwa_session_id TEXT DEFAULT '',
    connection_status TEXT DEFAULT 'disconnected',
    webhook_status TEXT DEFAULT 'not_configured',
    token_status TEXT DEFAULT 'not_set',
    last_validation_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_secrets (
    id TEXT PRIMARY KEY,
    whatsapp_account_id TEXT NOT NULL UNIQUE,
    encrypted_access_token TEXT,
    encrypted_app_secret TEXT,
    encrypted_verify_token TEXT,
    encrypted_openwa_api_key TEXT,
    token_expires_at TEXT,
    last_rotated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_webhook_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    whatsapp_account_id TEXT,
    event_type TEXT DEFAULT 'unknown',
    payload_json TEXT,
    delivery_status TEXT DEFAULT 'received',
    error_message TEXT,
    received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_api_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    whatsapp_account_id TEXT,
    direction TEXT DEFAULT 'outbound',
    endpoint TEXT,
    request_summary TEXT,
    response_summary TEXT,
    status_code INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    user_id TEXT,
    action_type TEXT NOT NULL,
    action TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    description TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL
);

-- Legacy tables referenced by setup.py seed cleanup
CREATE TABLE IF NOT EXISTS internal_notes (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS conversation_events (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS conversation_views (
    id TEXT PRIMARY KEY
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_case ON messages(case_id);
CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction);
CREATE INDEX IF NOT EXISTS idx_messages_sent ON messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_cases_conv ON cases(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_assigned ON cases(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_cases_active ON cases(is_active);
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_case_views_case ON case_views(case_id);
CREATE INDEX IF NOT EXISTS idx_case_notes_case ON case_notes(case_id);
CREATE INDEX IF NOT EXISTS idx_conv_contact ON conversations(contact_id);
CREATE INDEX IF NOT EXISTS idx_conv_tenant ON conversations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_profiles_tenant ON profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_needs_class ON messages(needs_classification);
-- Additional indexes for columns used in WHERE clauses
CREATE INDEX IF NOT EXISTS idx_wa_accounts_tenant ON whatsapp_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_wa_secrets_account ON whatsapp_secrets(whatsapp_account_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_tenant ON whatsapp_webhook_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_tenant ON whatsapp_api_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_account ON whatsapp_webhook_logs(whatsapp_account_id);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);
CREATE INDEX IF NOT EXISTS idx_whatsapp_accounts_phone ON whatsapp_accounts(phone_number_id);
"""


def _seed_test_users(conn):
    """Pre-seed with test users from test_credentials.md."""
    now = datetime.now(timezone.utc).isoformat()

    # Create tenants
    tenants = [
        ('t01000000-0000-0000-0000-000000000001', 'Auto Recanvis Catalunya', 'auto-recanvis', 'active', now),
        ('t02000000-0000-0000-0000-000000000002', 'BlockchainTools SL', 'blockchaintools', 'active', now),
    ]
    for t in tenants:
        try:
            conn.execute(
                'INSERT INTO tenants (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)', t
            )
        except sqlite3.IntegrityError:
            pass  # Already exists

    # Create users with hashed passwords
    users = [
        ('u01000000-0000-0000-0000-000000000001', 'Admin ARC', 'admin@workshoppartsdesk.com',
         hash_password('Admin123!'), 'admin', None, 'admin_arc', 1,
         't01000000-0000-0000-0000-000000000001', now),
        ('u02000000-0000-0000-0000-000000000002', 'Admin BT', 'info@blockchaintools.es',
         hash_password('Riullobregat$4'), 'admin', None, 'admin_bt', 1,
         't02000000-0000-0000-0000-000000000002', now),
        ('u03000000-0000-0000-0000-000000000003', 'Super Admin', 'superadmin@workshoppartsdesk.com',
         hash_password('SuperAdmin2026!'), 'super_admin', None, 'superadmin', 1, None, now),
        ('u04000000-0000-0000-0000-000000000004', 'Juanjo Ruiz', 'juanjo@auto-recanvis-cat.workshop',
         hash_password('Agent2026!'), 'agent', None, 'juanjo', 1,
         't01000000-0000-0000-0000-000000000001', now),
        ('u05000000-0000-0000-0000-000000000005', 'Albert Cliville', 'albert@workshoppartsdesk.com',
         hash_password('Agent2026!'), 'agent', None, 'albert', 1,
         't01000000-0000-0000-0000-000000000001', now),
    ]
    for u in users:
        try:
            conn.execute(
                '''INSERT INTO profiles
                   (id, full_name, email, password_hash, role, phone, username, is_active, tenant_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', u
            )
        except sqlite3.IntegrityError:
            pass  # Already exists

    # Also insert into _auth_users for login
    for u in users:
        try:
            conn.execute(
                'INSERT INTO _auth_users (id, email, password_hash) VALUES (?, ?, ?)',
                (u[0], u[2], u[3])
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()


def _migrate_schema(conn):
    """Add columns that may be missing on existing databases (safe to call multiple times)."""
    migrations = [
        "ALTER TABLE whatsapp_accounts ADD COLUMN connection_type TEXT DEFAULT 'meta'",
        "ALTER TABLE whatsapp_accounts ADD COLUMN openwa_server_url TEXT DEFAULT ''",
        "ALTER TABLE whatsapp_accounts ADD COLUMN openwa_session_id TEXT DEFAULT ''",
        "ALTER TABLE whatsapp_secrets ADD COLUMN encrypted_openwa_api_key TEXT",
        "ALTER TABLE contacts ADD COLUMN source TEXT DEFAULT ''",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists


def init_db(db_path: str = None):
    """Create schema and seed data on first run. Safe to call multiple times."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(SCHEMA_SQL)
    _migrate_schema(conn)  # Add any columns from newer versions
    conn.commit()

    # Check if already seeded
    existing = conn.execute("SELECT id FROM profiles LIMIT 1").fetchone()
    if not existing:
        _seed_test_users(conn)

    conn.close()

    # Ensure media directories exist
    for folder in ['incoming', 'outgoing']:
        (MEDIA_DIR / 'media' / folder).mkdir(parents=True, exist_ok=True)
