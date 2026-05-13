import pytest
import sqlite3
from datetime import datetime
from app import app
from database.db import init_db, get_db
from database.queries import insert_expense

import os
import tempfile

@pytest.fixture
def client():
    """Create a test client with a clean temporary file database for each test."""
    db_fd, db_path = tempfile.mkstemp()
    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    
    # Initialize the schema in the temp file
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    
    import database.db as db_module
    import database.queries as queries_module
    import app as app_module
    
    orig_get_db = db_module.get_db
    orig_seed_db = db_module.seed_db
    
    # Disable seeding during tests
    db_module.seed_db = lambda: None
    
    def mock_get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Monkeypatch get_db in all relevant namespaces
    db_module.get_db = mock_get_db
    if hasattr(queries_module, 'get_db'):
        queries_module.get_db = mock_get_db
    if hasattr(app_module, 'get_db'):
        app_module.get_db = mock_get_db

    with app.test_client() as client:
        with app.app_context():
            yield client

    # Cleanup
    db_module.get_db = orig_get_db
    db_module.seed_db = orig_seed_db
    os.close(db_fd)
    os.unlink(db_path)

def login(client, email="test@example.com", password="password123"):
    """Helper to register and log in a user."""
    client.post('/register', data={
        'name': 'Test User',
        'email': email,
        'password': password
    })
    return client.post('/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)

# ========================================================================
# Unit Tests
# ========================================================================

def test_insert_expense_valid(client):
    """Test insert_expense with valid data (Requirement: Unit tests)"""
    from database.db import add_user
    user_id = add_user("User 1", "user1@example.com", "pass123")
    
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
    assert expense_id is not None
    
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    assert row['amount'] == 50.0
    assert row['category'] == "Food"
    assert row['date'] == "2026-03-20"
    assert row['description'] == "Lunch"

def test_insert_expense_none_description(client):
    """Test insert_expense with None description (Requirement: Unit tests)"""
    from database.db import add_user
    user_id = add_user("User 2", "user2@example.com", "pass123")
    
    expense_id = insert_expense(user_id, 75.0, "Transport", "2026-03-21", None)
    assert expense_id is not None
    
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    assert row['description'] is None

# ========================================================================
# Route Tests - GET
# ========================================================================

def test_get_add_expense_unauthenticated(client):
    """GET /expenses/add redirects to login if not authenticated (Requirement: Route tests)"""
    response = client.get('/expenses/add')
    assert response.status_code == 302
    assert '/login' in response.location

def test_get_add_expense_authenticated(client):
    """GET /expenses/add returns 200 and form if authenticated (Requirement: Route tests)"""
    login(client)
    response = client.get('/expenses/add')
    assert response.status_code == 200
    assert b'<form' in response.data
    assert b'METHOD="POST"' in response.data.upper()
    # Check for categories
    for cat in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert cat.encode() in response.data

# ========================================================================
# Route Tests - POST
# ========================================================================

def test_post_add_expense_unauthenticated(client):
    """POST /expenses/add redirects to login if not authenticated (Requirement: Route tests)"""
    response = client.post('/expenses/add', data={
        'amount': '50.0', 'category': 'Food', 'date': '2026-03-20'
    })
    assert response.status_code == 302
    assert '/login' in response.location

def test_post_add_expense_valid(client):
    """POST /expenses/add works with valid data (Requirement: Route tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': '50.0',
        'category': 'Food',
        'date': '2026-03-20',
        'description': 'Lunch'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Should redirect to profile (landing page for now or profile if implemented)
    # The spec says redirect to /profile
    
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses").fetchone()
    assert row is not None
    assert row['amount'] == 50.0
    assert row['category'] == "Food"

def test_post_add_expense_missing_amount(client):
    """POST /expenses/add fails if amount is missing (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'category': 'Food',
        'date': '2026-03-20'
    })
    assert response.status_code == 200
    assert b'Amount is required' in response.data

def test_post_add_expense_zero_amount(client):
    """POST /expenses/add fails if amount is zero (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': '0',
        'category': 'Food',
        'date': '2026-03-20'
    })
    assert response.status_code == 200
    assert b'greater than zero' in response.data

def test_post_add_expense_non_numeric_amount(client):
    """POST /expenses/add fails if amount is non-numeric (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': 'abc',
        'category': 'Food',
        'date': '2026-03-20'
    })
    assert response.status_code == 200
    assert b'valid number' in response.data

def test_post_add_expense_invalid_category(client):
    """POST /expenses/add fails if category is invalid (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': '50.0',
        'category': 'Invalid',
        'date': '2026-03-20'
    })
    assert response.status_code == 200
    assert b'Invalid category' in response.data

def test_post_add_expense_invalid_date(client):
    """POST /expenses/add fails if date is invalid format (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': '50.0',
        'category': 'Food',
        'date': '2026/03/20' # Wrong format YYYY-MM-DD expected
    })
    assert response.status_code == 200
    assert b'Invalid date format' in response.data

def test_post_add_expense_no_description(client):
    """POST /expenses/add works without description (Requirement: Validation tests)"""
    login(client)
    response = client.post('/expenses/add', data={
        'amount': '50.0',
        'category': 'Food',
        'date': '2026-03-20',
        'description': ''
    }, follow_redirects=True)
    
    assert response.status_code == 200
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses").fetchone()
    assert row['description'] is None
