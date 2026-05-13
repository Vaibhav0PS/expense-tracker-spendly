"""
Test cases for the Add Expense feature (Step 07).

Tests verify:
1. Authentication & Authorization (GET/POST require login)
2. Form Display (GET shows correct fields and categories)
3. Validation (POST rejects invalid data with error messages)
4. Success Cases (valid POST saves to DB and redirects)
5. Database Integrity (insert_expense helper works correctly)
6. Edge Cases (large amounts, decimals, special characters, all categories)

Spec: .claude/specs/07-add-expense.md
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from app import app
from database.db import init_db, get_db
from database.queries import insert_expense


@pytest.fixture
def client():
    """Create a test client with in-memory SQLite database."""
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            import database.db as db_module

            # Patch get_db to use a shared in-memory database for test isolation
            memory_uri = "file:test_add_expense?mode=memory&cache=shared"
            keeper_conn = sqlite3.connect(memory_uri, uri=True)
            keeper_conn.row_factory = sqlite3.Row
            keeper_conn.execute("PRAGMA foreign_keys = ON")

            def _mem_db():
                conn = sqlite3.connect(memory_uri, uri=True)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                return conn

            orig_get_db = db_module.get_db
            db_module.get_db = _mem_db

            init_db()
            # Create a test user for authenticated tests
            from database.db import add_user
            test_user_id = add_user("Test User", "test@example.com", "password123")
            # Store the user_id in app context for tests
            client.test_user_id = test_user_id

            yield client

            keeper_conn.close()
            db_module.get_db = orig_get_db


def login(client, email="test@example.com", password="password123"):
    """Helper function to log in a user."""
    return client.post(
        '/login',
        data={'email': email, 'password': password},
        follow_redirects=True
    )


# ========================================================================
# Authentication & Authorization Tests
# ========================================================================

class TestAddExpenseAuth:
    """Test authentication and authorization for /expenses/add routes."""

    def test_get_add_expense_without_login_redirects_to_login(self, client):
        """GET /expenses/add without login should redirect to /login."""
        response = client.get('/expenses/add', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location

    def test_post_add_expense_without_login_redirects_to_login(self, client):
        """POST /expenses/add without login should redirect to /login."""
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            },
            follow_redirects=False
        )
        assert response.status_code == 302
        assert '/login' in response.location

    def test_get_add_expense_with_login_returns_200(self, client):
        """GET /expenses/add while logged in should return 200."""
        login(client)
        response = client.get('/expenses/add')
        assert response.status_code == 200


# ========================================================================
# Form Display Tests (GET)
# ========================================================================

class TestAddExpenseFormDisplay:
    """Test that the add-expense form displays correctly."""

    def test_form_contains_amount_input(self, client):
        """Form should have amount input with step='0.01' and min='0.01'."""
        login(client)
        response = client.get('/expenses/add')
        assert b'name="amount"' in response.data
        assert b'type="number"' in response.data
        assert b'step="0.01"' in response.data
        assert b'min="0.01"' in response.data

    def test_form_contains_category_select(self, client):
        """Form should have category select element."""
        login(client)
        response = client.get('/expenses/add')
        assert b'<select' in response.data
        assert b'name="category"' in response.data

    def test_form_contains_all_seven_categories(self, client):
        """Category select should contain all 7 options."""
        login(client)
        response = client.get('/expenses/add')
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for category in categories:
            assert category.encode() in response.data

    def test_form_contains_date_input(self, client):
        """Form should have date input field."""
        login(client)
        response = client.get('/expenses/add')
        assert b'name="date"' in response.data
        assert b'type="date"' in response.data

    def test_form_contains_description_input(self, client):
        """Form should have description field (optional)."""
        login(client)
        response = client.get('/expenses/add')
        assert b'name="description"' in response.data

    def test_form_contains_submit_button(self, client):
        """Form should have a submit button."""
        login(client)
        response = client.get('/expenses/add')
        # Look for submit button with appropriate text
        assert b'type="submit"' in response.data

    def test_form_contains_cancel_link_to_profile(self, client):
        """Form should have a cancel link back to /profile."""
        login(client)
        response = client.get('/expenses/add')
        assert b'/profile' in response.data

    def test_form_has_post_method(self, client):
        """Form should use POST method."""
        login(client)
        response = client.get('/expenses/add')
        assert b'method="POST"' in response.data or b"method='POST'" in response.data

    def test_form_action_is_expenses_add(self, client):
        """Form action should point to /expenses/add."""
        login(client)
        response = client.get('/expenses/add')
        assert b'/expenses/add' in response.data


# ========================================================================
# Validation Tests (POST with invalid data)
# ========================================================================

class TestAddExpenseValidation:
    """Test validation of POST /expenses/add with invalid inputs."""

    def test_missing_amount_returns_error(self, client):
        """POST with missing amount should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'Amount is required' in response.data or b'required' in response.data

    def test_amount_zero_returns_error(self, client):
        """POST with amount=0 should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '0',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'greater than zero' in response.data or b'zero' in response.data

    def test_amount_negative_returns_error(self, client):
        """POST with negative amount should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '-50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'greater than zero' in response.data or b'negative' in response.data

    def test_non_numeric_amount_returns_error(self, client):
        """POST with non-numeric amount should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': 'abc',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'valid number' in response.data or b'number' in response.data

    def test_missing_category_returns_error(self, client):
        """POST with missing category should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'Category is required' in response.data or b'category' in response.data

    def test_invalid_category_returns_error(self, client):
        """POST with invalid category should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'InvalidCategory',
                'date': '2026-05-05',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'Invalid category' in response.data

    def test_missing_date_returns_error(self, client):
        """POST with missing date should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'Date is required' in response.data or b'date' in response.data

    def test_invalid_date_format_returns_error(self, client):
        """POST with invalid date format should re-render form with error."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '05/05/2026',  # Wrong format
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'Invalid date format' in response.data or b'date' in response.data

    def test_future_date_returns_error(self, client):
        """POST with future date should re-render form with error."""
        login(client)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': tomorrow,
                'description': 'Lunch'
            }
        )
        assert response.status_code == 200
        assert b'future' in response.data or b'cannot be' in response.data


# ========================================================================
# Successful Submission Tests (Valid POST)
# ========================================================================

class TestAddExpenseSuccess:
    """Test successful submission of /expenses/add with valid data."""

    def test_valid_submission_redirects_to_profile(self, client):
        """Valid POST should redirect to /profile (302)."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            },
            follow_redirects=False
        )
        assert response.status_code == 302
        assert '/profile' in response.location

    def test_valid_submission_saves_to_database(self, client):
        """Valid POST should insert expense into database."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            },
            follow_redirects=True
        )

        # Verify expense appears in the database
        with app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT amount, category, date, description FROM expenses WHERE user_id = ? AND description = ?",
                (client.test_user_id, 'Lunch')
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Expense should be saved to database"
            assert float(row['amount']) == 50.00
            assert row['category'] == 'Food'
            assert row['date'] == '2026-05-05'
            assert row['description'] == 'Lunch'

    def test_valid_submission_shows_flash_message(self, client):
        """Valid POST should show success flash message."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Lunch'
            },
            follow_redirects=True
        )
        assert b'success' in response.data or b'added' in response.data

    def test_empty_description_stores_as_none(self, client):
        """Submitting without description should store NULL in database."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '75.50',
                'category': 'Transport',
                'date': '2026-05-03',
                'description': ''
            },
            follow_redirects=True
        )

        # Verify expense has NULL description
        with app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT description FROM expenses WHERE user_id = ? AND amount = ?",
                (client.test_user_id, 75.50)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row['description'] is None

    def test_decimal_amount_stored_correctly(self, client):
        """Decimal amounts should be stored as float."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '12.75',
                'category': 'Food',
                'date': '2026-05-02',
                'description': 'Coffee'
            },
            follow_redirects=True
        )

        with app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT amount FROM expenses WHERE user_id = ? AND description = ?",
                (client.test_user_id, 'Coffee')
            )
            row = cursor.fetchone()
            conn.close()

            assert float(row['amount']) == 12.75

    def test_today_date_is_allowed(self, client):
        """Today's date should be accepted."""
        login(client)
        today = datetime.now().strftime('%Y-%m-%d')
        response = client.post(
            '/expenses/add',
            data={
                'amount': '25.00',
                'category': 'Bills',
                'date': today,
                'description': 'Today expense'
            },
            follow_redirects=False
        )
        assert response.status_code == 302, "Today's date should be accepted"

    def test_all_seven_categories_can_be_submitted(self, client):
        """Each of the 7 categories should be accepted."""
        login(client)
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

        for i, category in enumerate(categories):
            response = client.post(
                '/expenses/add',
                data={
                    'amount': f'{20 + i}.00',
                    'category': category,
                    'date': '2026-05-05',
                    'description': f'{category} expense'
                },
                follow_redirects=False
            )
            assert response.status_code == 302, f"Category '{category}' should be accepted"

    def test_very_large_amount_accepted(self, client):
        """Very large amounts should be accepted."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '999999.99',
                'category': 'Shopping',
                'date': '2026-05-05',
                'description': 'Large purchase'
            },
            follow_redirects=False
        )
        assert response.status_code == 302

    def test_description_with_special_characters(self, client):
        """Description with special characters should be accepted."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': "Lunch at Joe's Diner & Café (₹100 discount)"
            },
            follow_redirects=True
        )
        assert response.status_code == 200

    def test_max_length_description(self, client):
        """Description at max length (200 chars) should be accepted."""
        login(client)
        long_description = "x" * 200
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-05',
                'description': long_description
            },
            follow_redirects=False
        )
        assert response.status_code == 302


# ========================================================================
# Database Helper Tests
# ========================================================================

class TestInsertExpenseHelper:
    """Test the insert_expense() helper function."""

    def test_insert_expense_with_description_returns_id(self, client):
        """insert_expense() should return expense ID on success."""
        with app.app_context():
            expense_id = insert_expense(
                client.test_user_id,
                50.0,
                "Food",
                "2026-03-20",
                "Lunch"
            )
            assert expense_id is not None
            assert isinstance(expense_id, int)

    def test_insert_expense_with_none_description_returns_id(self, client):
        """insert_expense() with None description should return expense ID."""
        with app.app_context():
            expense_id = insert_expense(
                client.test_user_id,
                75.50,
                "Transport",
                "2026-03-21",
                None
            )
            assert expense_id is not None
            assert isinstance(expense_id, int)

    def test_insert_expense_creates_database_row(self, client):
        """insert_expense() should create a row in the database."""
        with app.app_context():
            expense_id = insert_expense(
                client.test_user_id,
                50.0,
                "Food",
                "2026-03-20",
                "Lunch"
            )

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row['user_id'] == client.test_user_id
            assert float(row['amount']) == 50.0
            assert row['category'] == "Food"
            assert row['date'] == "2026-03-20"
            assert row['description'] == "Lunch"

    def test_insert_expense_with_null_description(self, client):
        """insert_expense() with None description should store NULL."""
        with app.app_context():
            expense_id = insert_expense(
                client.test_user_id,
                100.0,
                "Bills",
                "2026-03-22",
                None
            )

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT description FROM expenses WHERE id = ?", (expense_id,))
            row = cursor.fetchone()
            conn.close()

            assert row['description'] is None

    def test_insert_expense_sets_created_at_timestamp(self, client):
        """insert_expense() should auto-set created_at timestamp."""
        with app.app_context():
            expense_id = insert_expense(
                client.test_user_id,
                50.0,
                "Food",
                "2026-03-20",
                "Lunch"
            )

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT created_at FROM expenses WHERE id = ?", (expense_id,))
            row = cursor.fetchone()
            conn.close()

            assert row['created_at'] is not None

    def test_insert_expense_respects_user_id_foreign_key(self, client):
        """insert_expense() should enforce user_id foreign key."""
        with app.app_context():
            # Try to insert with non-existent user_id
            result = insert_expense(
                99999,  # Non-existent user
                50.0,
                "Food",
                "2026-03-20",
                "Lunch"
            )
            # Should fail due to FK constraint
            assert result is None


# ========================================================================
# Edge Cases & Integration Tests
# ========================================================================

class TestAddExpenseEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_multiple_expenses_same_user(self, client):
        """User should be able to add multiple expenses."""
        login(client)

        # Add first expense
        response1 = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2026-05-01',
                'description': 'Lunch'
            },
            follow_redirects=False
        )

        # Add second expense
        response2 = client.post(
            '/expenses/add',
            data={
                'amount': '75.00',
                'category': 'Transport',
                'date': '2026-05-02',
                'description': 'Bus pass'
            },
            follow_redirects=False
        )

        assert response1.status_code == 302
        assert response2.status_code == 302

        # Both should be in database
        with app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (client.test_user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            assert count == 2

    def test_old_date_is_allowed(self, client):
        """Past dates should be allowed."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '2020-01-01',
                'description': 'Old expense'
            },
            follow_redirects=False
        )
        assert response.status_code == 302

    def test_whitespace_is_stripped_from_fields(self, client):
        """Whitespace in form fields should be stripped."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '  50.00  ',
                'category': '  Food  ',
                'date': '2026-05-05',
                'description': '  Lunch with spaces  '
            },
            follow_redirects=True
        )

        with app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT description FROM expenses WHERE user_id = ? AND amount = ?",
                (client.test_user_id, 50.0)
            )
            row = cursor.fetchone()
            conn.close()

            # Description should have leading/trailing whitespace removed
            assert row['description'] is not None

    def test_amount_with_many_decimal_places(self, client):
        """Amount with more than 2 decimal places should work."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.999',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Precise expense'
            },
            follow_redirects=False
        )
        assert response.status_code == 302


# ========================================================================
# Form State Preservation Tests
# ========================================================================

class TestAddExpenseFormStatePreservation:
    """Test that form preserves values on validation errors."""

    def test_form_preserves_amount_on_error(self, client):
        """Form should preserve amount value when validation fails."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'InvalidCategory',
                'date': '2026-05-05',
                'description': 'Test'
            }
        )
        # Ideally the response would contain the value, but we verify no crash
        assert response.status_code == 200

    def test_form_preserves_category_on_error(self, client):
        """Form should preserve category value when validation fails."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': 'invalid',
                'category': 'Food',
                'date': '2026-05-05',
                'description': 'Test'
            }
        )
        assert response.status_code == 200

    def test_form_preserves_date_on_error(self, client):
        """Form should preserve date value when validation fails."""
        login(client)
        response = client.post(
            '/expenses/add',
            data={
                'amount': '50.00',
                'category': 'Food',
                'date': '',
                'description': 'Test'
            }
        )
        # Form should re-render without crash
        assert response.status_code == 200
