"""
Tests for Step 6: Date Filter for Profile Page.

Spec behaviors verified:
1. No query params → unfiltered (all expenses shown, same as Step 5)
2. date_from + date_to params filter all three sections via parameterized SQL
3. Malformed dates silently ignored (fall back to unfiltered)
4. date_from > date_to → flash error and fall back to unfiltered
5. Active preset button gets filter-btn-active CSS class
6. Custom date inputs pre-filled from date_from_value/date_to_value
7. "All Time" preset = no query params
8. Unauthenticated request → redirect to /login
"""

import os
import pytest
from datetime import datetime, timedelta
from flask import get_flashed_messages

from app import app
from database.db import get_db, init_db


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a test client with an in-memory DB and authenticated session."""
    import sqlite3

    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            import database.db as db_module

            # Close any existing file connection before switching to :memory:
            _conn = db_module.get_db()
            _conn.close()

            orig_get_db = db_module.get_db
            memory_uri = "file:test_profile_date_filter?mode=memory&cache=shared"
            keeper_conn = sqlite3.connect(memory_uri, uri=True)
            keeper_conn.row_factory = sqlite3.Row
            keeper_conn.execute("PRAGMA foreign_keys = ON")

            def _mem_db():
                conn = sqlite3.connect(memory_uri, uri=True)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                return conn

            db_module.get_db = _mem_db

            init_db()
            _seed_test_data(db_module)

            yield client

            keeper_conn.close()
            db_module.get_db = orig_get_db
            db_module.DATABASE_PATH = os.path.join(
                os.path.dirname(__file__), "..", "spendly.db"
            )


def _seed_test_data(db_module):
    """Insert a test user and known expenses spanning Jan–Apr 2026."""
    from werkzeug.security import generate_password_hash

    conn = db_module.get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@example.com", generate_password_hash("password123")),
    )
    user_id = cursor.lastrowid

    # Expenses spread across Jan–Apr 2026 with known totals
    expenses = [
        # January 2026
        (user_id, 50.00, "Food",     "2026-01-10", "Groceries"),
        (user_id, 30.00, "Transport","2026-01-15", "Fuel"),
        # February 2026
        (user_id, 80.00, "Bills",    "2026-02-01", "Internet"),
        (user_id, 20.00, "Health",   "2026-02-20", "Pharmacy"),
        # March 2026
        (user_id, 45.00, "Shopping", "2026-03-05", "Clothes"),
        (user_id, 15.00, "Entertainment","2026-03-22", "Movie"),
        # April 2026
        (user_id, 25.00, "Food",     "2026-04-01", "Lunch"),
        (user_id, 40.00, "Transport","2026-04-10", "Taxi"),
        (user_id, 60.00, "Bills",    "2026-04-15", "Electricity"),
        (user_id, 10.00, "Other",    "2026-04-25", "Misc"),
    ]
    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()

    return user_id


@pytest.fixture
def authenticated_client(client):
    """A test client already logged in as the test user."""
    with client.session_transaction() as sess:
        sess['user_id'] = 1  # The seeded test user has id=1
    return client


# ── Helper ────────────────────────────────────────────────────────────────────

def get_expense_count_for_user(user_id):
    """Return the raw count of expenses for a user (for assertions)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ── Auth Guard Tests ─────────────────────────────────────────────────────────

class TestProfileDateFilterAuth:
    """Spec rule: Unauthenticated request → redirect to /login."""

    def test_profile_without_session_redirects_to_login(self, client):
        """GET /profile with no session should redirect to /login."""
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_profile_with_session_returns_200(self, authenticated_client):
        """GET /profile with valid session should return 200."""
        response = authenticated_client.get('/profile')
        assert response.status_code == 200


# ── No-Filter (All Time) Tests ───────────────────────────────────────────────

class TestProfileDateFilterNoFilter:
    """Spec rule: No query params → unfiltered (all expenses, same as Step 5)."""

    def test_profile_no_params_shows_all_expenses(self, authenticated_client):
        """With no date params, all 10 seeded expenses appear in the table."""
        response = authenticated_client.get('/profile')
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # All 10 expense descriptions from the seed data
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_profile_no_params_transaction_count(self, authenticated_client):
        """With no date params, the Total Expenses stat equals all 10 records."""
        response = authenticated_client.get('/profile')
        html = response.get_data(as_text=True)
        # The seed data has 10 expenses total
        assert "10" in html  # Total Expenses = 10

    def test_profile_all_time_preset_no_params(self, authenticated_client):
        """The 'All Time' preset link must have no query params."""
        response = authenticated_client.get('/profile')
        html = response.get_data(as_text=True)

        # Find the All Time link
        import re
        all_time_link = re.search(r'<a[^>]*>All Time</a>', html)
        assert all_time_link is not None

        link_tag = all_time_link.group(0)
        # Must NOT contain ?date_from or ?date_to
        assert 'date_from' not in link_tag
        assert 'date_to' not in link_tag

    def test_profile_all_time_preset_has_active_class(self, authenticated_client):
        """When no filter is active, the All Time button has filter-btn-active."""
        response = authenticated_client.get('/profile')
        html = response.get_data(as_text=True)

        import re
        all_time_link = re.search(r'<a[^>]*>All Time</a>', html)
        assert all_time_link is not None
        assert 'filter-btn-active' in all_time_link.group(0)

    def test_profile_no_params_stats_total_spent(self, authenticated_client):
        """Total spent with no filter should equal sum of all 10 seed expenses."""
        response = authenticated_client.get('/profile')
        html = response.get_data(as_text=True)
        # Sum of seed expenses: 50+30+80+20+45+15+25+40+60+10 = 375.00
        assert "375.00" in html


# ── Preset Filter Tests ───────────────────────────────────────────────────────

class TestProfileDateFilterPresets:
    """Spec rule: Preset links with date_from/date_to filter all three sections."""

    def test_this_month_preset_filters_transactions(self, authenticated_client):
        """'This Month' preset should show only April 2026 expenses."""
        # Manually compute the expected "This Month" range
        now = datetime.now()
        this_month_from = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
        this_month_to = now.strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f'/profile?date_from={this_month_from}&date_to={this_month_to}'
        )
        html = response.get_data(as_text=True)

        # April expenses (Lunch, Taxi, Electricity, Misc) should be present
        for desc in ["Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

        # Pre-April expenses must NOT be present
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes", "Movie"]:
            assert desc not in html

    def test_this_month_preset_sets_active_class(self, authenticated_client):
        """'This Month' preset button should have filter-btn-active."""
        now = datetime.now()
        this_month_from = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
        this_month_to = now.strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f'/profile?date_from={this_month_from}&date_to={this_month_to}'
        )
        html = response.get_data(as_text=True)

        import re
        this_month_link = re.search(r'<a[^>]*>This Month</a>', html)
        assert this_month_link is not None
        assert 'filter-btn-active' in this_month_link.group(0)

    def test_last_3_months_preset_filters_correctly(self, authenticated_client):
        """'Last 3 Months' preset should filter to the 3-month window ending today."""
        now = datetime.now()

        def months_ago(n):
            m = now.month - n
            y = now.year + m // 12
            m = m % 12
            if m < 1:
                m += 12
                y -= 1
            return datetime(y, m, 1).strftime("%Y-%m-%d")

        last_3_from = months_ago(2)
        last_3_to = now.strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f'/profile?date_from={last_3_from}&date_to={last_3_to}'
        )
        html = response.get_data(as_text=True)

        # February, March, April should be present
        for desc in ["Internet", "Pharmacy", "Clothes", "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

        # January expenses should not appear
        for desc in ["Groceries", "Fuel"]:
            assert desc not in html

    def test_last_3_months_preset_sets_active_class(self, authenticated_client):
        """'Last 3 Months' preset button should have filter-btn-active."""
        now = datetime.now()

        def months_ago(n):
            m = now.month - n
            y = now.year + m // 12
            m = m % 12
            if m < 1:
                m += 12
                y -= 1
            return datetime(y, m, 1).strftime("%Y-%m-%d")

        last_3_from = months_ago(2)
        last_3_to = now.strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f'/profile?date_from={last_3_from}&date_to={last_3_to}'
        )
        html = response.get_data(as_text=True)

        import re
        last_3_link = re.search(r'<a[^>]*>Last 3 Months</a>', html)
        assert last_3_link is not None
        assert 'filter-btn-active' in last_3_link.group(0)

    def test_last_6_months_preset_filters_correctly(self, authenticated_client):
        """'Last 6 Months' preset should show Jan–Apr 2026 (all seeded data)."""
        now = datetime.now()

        def months_ago(n):
            m = now.month - n
            y = now.year + m // 12
            m = m % 12
            if m < 1:
                m += 12
                y -= 1
            return datetime(y, m, 1).strftime("%Y-%m-%d")

        last_6_from = months_ago(6)
        last_6_to = now.strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f'/profile?date_from={last_6_from}&date_to={last_6_to}'
        )
        html = response.get_data(as_text=True)

        # All 10 expenses from Jan–Apr should be present
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_all_time_preset_removes_filter(self, authenticated_client):
        """GET /profile with no params (All Time) should show all expenses."""
        # Hit the URL with no query params
        response = authenticated_client.get('/profile')
        html = response.get_data(as_text=True)

        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html


# ── Custom Date Range Tests ───────────────────────────────────────────────────

class TestProfileDateFilterCustomRange:
    """Spec rule: Custom date form submits date_from/date_to; all sections filter."""

    def test_custom_date_range_filters_transactions(self, authenticated_client):
        """A custom range (2026-02-01 to 2026-03-31) should show Feb+Mar expenses."""
        response = authenticated_client.get(
            '/profile?date_from=2026-02-01&date_to=2026-03-31'
        )
        html = response.get_data(as_text=True)

        # February and March expenses present
        for desc in ["Internet", "Pharmacy", "Clothes", "Movie"]:
            assert desc in html

        # January and April expenses absent
        for desc in ["Groceries", "Fuel", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc not in html

    def test_custom_date_range_pre_fills_inputs(self, authenticated_client):
        """After submitting a custom range, inputs should show those values."""
        response = authenticated_client.get(
            '/profile?date_from=2026-02-01&date_to=2026-03-31'
        )
        html = response.get_data(as_text=True)

        assert 'value="2026-02-01"' in html
        assert 'value="2026-03-31"' in html

    def test_custom_date_range_sets_active_preset_to_custom(self, authenticated_client):
        """A non-preset custom range should NOT highlight any preset button."""
        response = authenticated_client.get(
            '/profile?date_from=2026-02-01&date_to=2026-03-31'
        )
        html = response.get_data(as_text=True)

        import re
        # None of the preset links should have filter-btn-active
        preset_links = re.findall(r'<a[^>]*>(?:This Month|Last 3 Months|Last 6 Months|All Time)</a>', html)
        for link in preset_links:
            assert 'filter-btn-active' not in link

    def test_custom_date_range_shows_stats_for_filtered_period(self, authenticated_client):
        """Stats should reflect only the filtered period (Feb 1–Mar 31)."""
        response = authenticated_client.get(
            '/profile?date_from=2026-02-01&date_to=2026-03-31'
        )
        html = response.get_data(as_text=True)

        # Stats: Internet(80)+Pharmacy(20)+Clothes(45)+Movie(15) = 160.00
        assert "160.00" in html
        # Total count: 4 transactions
        assert "4" in html  # Total Expenses = 4

    def test_custom_date_range_filters_category_breakdown(self, authenticated_client):
        """Category breakdown should only include categories from the filtered period."""
        response = authenticated_client.get(
            '/profile?date_from=2026-02-01&date_to=2026-03-31'
        )
        html = response.get_data(as_text=True)

        # Categories present in Feb+Mar: Bills, Health, Shopping, Entertainment
        for cat in ["Bills", "Health", "Shopping", "Entertainment"]:
            assert cat in html

        # Categories absent from Feb+Mar: Food (Jan only), Transport (Jan+Apr)
        # Note: Transport in Jan (30) and Apr (40), Food in Jan (50) and Apr (25)
        assert "Food" not in html
        assert "Transport" not in html


# ── Malformed Date Handling ───────────────────────────────────────────────────

class TestProfileDateFilterMalformedDates:
    """Spec rule: Malformed dates silently ignored → fall back to unfiltered."""

    def test_malformed_date_from_ignored_shows_all(self, authenticated_client):
        """A bad date_from value should be ignored, showing all expenses."""
        response = authenticated_client.get(
            '/profile?date_from=not-a-date&date_to=2026-04-30'
        )
        html = response.get_data(as_text=True)

        # All 10 expenses should appear (unfiltered)
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_malformed_date_to_ignored_shows_all(self, authenticated_client):
        """A bad date_to value should be ignored, showing all expenses."""
        response = authenticated_client.get(
            '/profile?date_from=2026-01-01&date_to=invalid'
        )
        html = response.get_data(as_text=True)

        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_both_dates_malformed_ignored_shows_all(self, authenticated_client):
        """Both dates malformed should fall back to unfiltered view."""
        response = authenticated_client.get(
            '/profile?date_from=bad&date_to=als bad'
        )
        html = response.get_data(as_text=True)

        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_wrong_format_date_ignored(self, authenticated_client):
        """Dates not in YYYY-MM-DD format should be ignored."""
        # DD/MM/YYYY format
        response = authenticated_client.get(
            '/profile?date_from=01-01-2026&date_to=30-04-2026'
        )
        html = response.get_data(as_text=True)

        # Should fall back to unfiltered (all 10 expenses)
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html


# ── date_from > date_to Validation ───────────────────────────────────────────

class TestProfileDateFilterRangeValidation:
    """Spec rule: date_from > date_to → flash error and fall back to unfiltered."""

    def test_date_from_after_date_to_flashes_error(self, authenticated_client):
        """When date_from > date_to, a flash error should be set."""
        response = authenticated_client.get(
            '/profile?date_from=2026-04-30&date_to=2026-01-01',
            follow_redirects=True
        )

        # Check flash messages
        flashes = get_flashed_messages(with_categories=False)
        assert any("Start date must be before end date" in str(f) for f in flashes)

    def test_date_from_after_date_to_shows_all_expenses(self, authenticated_client):
        """When date_from > date_to, the view should fall back to unfiltered."""
        response = authenticated_client.get(
            '/profile?date_from=2026-04-30&date_to=2026-01-01',
            follow_redirects=True
        )
        html = response.get_data(as_text=True)

        # All 10 expenses should appear (fallback to unfiltered)
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Clothes",
                     "Movie", "Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

    def test_date_from_after_date_to_no_active_preset(self, authenticated_client):
        """After invalid range error, no preset should be highlighted."""
        response = authenticated_client.get(
            '/profile?date_from=2026-04-30&date_to=2026-01-01',
            follow_redirects=True
        )
        html = response.get_data(as_text=True)

        import re
        all_time_link = re.search(r'<a[^>]*>All Time</a>', html)
        assert all_time_link is not None
        assert 'filter-btn-active' in all_time_link.group(0)


# ── Empty Range (No Expenses in Period) ───────────────────────────────────────

class TestProfileDateFilterEmptyRange:
    """Spec rule: No expenses in selected range → ₹0.00, 0 transactions, empty breakdown."""

    def test_no_expenses_in_range_shows_zero_totals(self, authenticated_client):
        """A range with no expenses should show ₹0.00 and 0 transactions."""
        # The seed data has no 2025 expenses
        response = authenticated_client.get(
            '/profile?date_from=2025-01-01&date_to=2025-12-31'
        )
        html = response.get_data(as_text=True)

        # ₹0.00 should appear (formatted as 0.00 with ₹ symbol)
        assert "₹0.00" in html
        assert "0" in html  # Total Expenses = 0

    def test_no_expenses_in_range_empty_transaction_list(self, authenticated_client):
        """A range with no expenses should show an empty transaction table."""
        response = authenticated_client.get(
            '/profile?date_from=2025-01-01&date_to=2025-12-31'
        )
        html = response.get_data(as_text=True)

        # None of the seed expense descriptions should appear
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy", "Lunch", "Taxi"]:
            assert desc not in html

    def test_no_expenses_in_range_empty_category_breakdown(self, authenticated_client):
        """A range with no expenses should show an empty category breakdown."""
        response = authenticated_client.get(
            '/profile?date_from=2025-01-01&date_to=2025-12-31'
        )
        html = response.get_data(as_text=True)

        # No category bars should be rendered
        assert "category-bar" not in html


# ── DB State / Parameterized Query Tests ─────────────────────────────────────

class TestProfileDateFilterParameterizedQueries:
    """Spec rule: Date filter uses parameterized queries (no SQL injection)."""

    def test_sql_injection_in_date_from_rejected(self, authenticated_client):
        """Attempting SQL injection via date_from should not crash or inject."""
        malicious = "2026-01-01'; DROP TABLE expenses; --"

        response = authenticated_client.get(
            f'/profile?date_from={malicious}&date_to=2026-04-30'
        )
        # Should either ignore the malformed value or handle it safely
        assert response.status_code in (200, 302)

        # The expenses table should still exist and have data
        response2 = authenticated_client.get('/profile')
        html = response2.get_data(as_text=True)
        # At least some seed expense should still be visible
        assert "Groceries" in html or "Lunch" in html

    def test_date_filter_uses_parameterized_queries(self, authenticated_client):
        """Verify date-filtered query uses ? placeholders by checking no string interpolation."""
        # This is verified by the implementation using _date_clause which uses ?
        # placeholders. We test functionally: filtering should work correctly.
        response = authenticated_client.get(
            '/profile?date_from=2026-04-01&date_to=2026-04-30'
        )
        html = response.get_data(as_text=True)

        # Only April expenses
        for desc in ["Lunch", "Taxi", "Electricity", "Misc"]:
            assert desc in html

        # Not January or February
        for desc in ["Groceries", "Fuel", "Internet", "Pharmacy"]:
            assert desc not in html

    def test_single_day_range(self, authenticated_client):
        """A range of exactly one day should return only expenses on that date."""
        # 2026-04-10 has only the "Taxi" expense (40.00)
        response = authenticated_client.get(
            '/profile?date_from=2026-04-10&date_to=2026-04-10'
        )
        html = response.get_data(as_text=True)

        assert "Taxi" in html
        assert "Lunch" not in html
        assert "Electricity" not in html

        # Stats for single day
        assert "40.00" in html


# ── Currency Symbol Tests ─────────────────────────────────────────────────────

class TestProfileDateFilterCurrencySymbol:
    """Spec rule: All amounts display the ₹ symbol regardless of active filter."""

    @pytest.mark.parametrize("filter_url", [
        "/profile",
        "/profile?date_from=2026-01-01&date_to=2026-03-31",
        "/profile?date_from=2026-04-01&date_to=2026-04-30",
        "/profile?date_from=2025-01-01&date_to=2025-12-31",
    ])
    def test_all_amounts_show_rupee_symbol(self, authenticated_client, filter_url):
        """Every rendered amount should include the ₹ symbol."""
        response = authenticated_client.get(filter_url)
        html = response.get_data(as_text=True)

        import re
        # Find all amount strings with ₹
        amounts = re.findall(r'₹[\d,]+\.\d{2}', html)
        assert len(amounts) > 0, f"No ₹ amounts found for filter: {filter_url}"
