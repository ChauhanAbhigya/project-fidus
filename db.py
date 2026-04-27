import sqlite3

DB_NAME = "parts.db"

# ---------------- CONNECTION ----------------
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# ---------------- INIT DB ----------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ---------------- USERS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # ---------------- OFFER ITEMS (EMPLOYEE-WISE) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offer_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        brand TEXT,
        part_no TEXT,
        qty REAL,
        price REAL,
        amount REAL
    )
    """)

    # ---------------- LOGS TABLE (FIX ADDED) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()