import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "spendly.db")


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 12.50, "Food", "2026-04-01", "Lunch at campus cafeteria"),
        (user_id, 45.00, "Transport", "2026-04-03", "Monthly bus pass"),
        (user_id, 89.99, "Bills", "2026-04-05", "Electricity bill"),
        (user_id, 25.00, "Health", "2026-04-07", "Pharmacy"),
        (user_id, 15.99, "Entertainment", "2026-04-09", "Movie streaming subscription"),
        (user_id, 67.50, "Shopping", "2026-04-11", "Textbooks"),
        (user_id, 8.00, "Food", "2026-04-13", "Coffee and snacks"),
        (user_id, 22.00, "Other", "2026-04-15", "Miscellaneous"),
    ]

    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )

    conn.commit()
    conn.close()


def add_user(name, email, password):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, password_hash FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
