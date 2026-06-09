import os, sqlite3

DB_PATH = os.environ.get("DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "event.db"))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_connection(); cur = conn.cursor()

    # ── CORE TABLES ───────────────────────────────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE, password TEXT,
        phone TEXT, college TEXT, degree TEXT,
        google_id TEXT, avatar TEXT,
        reset_token TEXT, reset_token_expiry TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, date TEXT, time TEXT, location TEXT,
        image TEXT, category TEXT,
        description TEXT DEFAULT '',
        seats INTEGER DEFAULT 100,
        fee INTEGER DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, user_name TEXT, age TEXT,
        college TEXT, degree TEXT, phone TEXT,
        registered_by TEXT, attended INTEGER DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, user_name TEXT,
        rating TEXT, message TEXT)""")

    # ── NEW FEATURE TABLES ────────────────────────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS notifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS announcements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, message TEXT,
        priority TEXT DEFAULT 'normal',
        created_at TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS wishlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, event_id INTEGER,
        UNIQUE(user_id, event_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, event_id INTEGER,
        created_at TEXT,
        UNIQUE(user_id, event_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS comments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, user_name TEXT,
        comment TEXT, created_at TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS contact_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, subject TEXT,
        message TEXT, created_at TEXT)""")

    # ── SAFE MIGRATIONS (add columns if missing) ──────────────────────────────
    migrations = [
        "ALTER TABLE events ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE events ADD COLUMN seats INTEGER DEFAULT 100",
        "ALTER TABLE events ADD COLUMN fee INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN phone TEXT",
        "ALTER TABLE users ADD COLUMN college TEXT",
        "ALTER TABLE users ADD COLUMN degree TEXT",
        "ALTER TABLE users ADD COLUMN reset_token TEXT",
        "ALTER TABLE users ADD COLUMN reset_token_expiry TEXT",
        "ALTER TABLE registrations ADD COLUMN phone TEXT",
        "ALTER TABLE registrations ADD COLUMN registered_by TEXT",
        "ALTER TABLE registrations ADD COLUMN attended INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try: cur.execute(sql)
        except: pass

    conn.commit(); conn.close()

# Keep for backward compatibility
def create_new_tables():
    create_tables()
