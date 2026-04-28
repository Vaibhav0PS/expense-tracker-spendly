from datetime import datetime
from database.db import get_db


def _format_inr(amount):
    """Format a number as Indian Rupee with ₹ symbol and comma separator."""
    return f"\u20b9{amount:,.2f}"


def _category_cls(category):
    """Return a CSS-safe class name from a category string."""
    return category.lower().replace(" ", "").replace("&", "")


def _format_date(date_str):
    """Format ISO date string as 'DD Mon YYYY' (e.g., '17 Apr 2026')."""
    try:
        d = datetime.fromisoformat(date_str)
        return d.strftime("%d %b %Y")
    except ValueError:
        return date_str


def get_user_profile(user_id):
    """
    Return user profile dict for the profile page sidebar.

    Returns dict with:
      - name, email, member_since (formatted "Month YYYY")
      - avatar_initials (first letter of each word, uppercase, max 2)

    Returns None if user not found.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    name = row["name"]
    email = row["email"]
    created_at = row["created_at"]

    # Member since: "Month YYYY"
    try:
        joined = datetime.fromisoformat(created_at)
        member_since = joined.strftime("%B %Y")
    except ValueError:
        member_since = "Unknown"

    # Avatar initials: first letter of each word, max 2
    initials = "".join(part[0].upper() for part in name.split()[:2])

    return {
        "name": name,
        "email": email,
        "member_since": member_since,
        "avatar_initials": initials,
    }


def get_summary_stats(user_id):
    """
    Return summary stats dict for the profile page stats row.

    Returns dict with:
      - total_spent: formatted "₹X,XXX.XX"
      - monthly_spending: formatted "₹X,XXX.XX" (current calendar month)
      - transaction_count: int
      - top_category: string or "—" if no expenses
    """
    conn = get_db()
    cursor = conn.cursor()

    # Total spent and transaction count
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    transaction_count = row[0]
    total_spent = row[1]

    # Monthly spending (current calendar month)
    now = datetime.now()
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) = ?",
        (user_id, now.strftime("%Y-%m")),
    )
    monthly_spent = cursor.fetchone()[0]

    # Top category (highest total)
    cursor.execute(
        """
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
        """,
        (user_id,),
    )
    top_row = cursor.fetchone()
    top_category = top_row["category"] if top_row else "—"

    conn.close()

    return {
        "total_spent": _format_inr(total_spent),
        "monthly_spending": _format_inr(monthly_spent),
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def get_recent_transactions(user_id, limit=10):
    """
    Return list of recent transactions, newest first.

    Each dict has: date, description, category, amount, cls
    Amount is formatted as "₹X,XXX.XX".
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date, description, category, amount
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "date": _format_date(row["date"]),
            "desc": row["description"] or "",
            "category": row["category"],
            "amount": "-" + _format_inr(row["amount"]),
            "cls": _category_cls(row["category"]),
        })
    return transactions


def get_category_breakdown(user_id):
    """
    Return category breakdown list ordered by amount descending.

    Each dict has: name, amount, pct, cls
    - amount is formatted as "₹X,XXX"
    - pct is an integer (0-100) summing to 100 across all categories
    - cls is a CSS-safe class name
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (user_id,),
    )
    total = cursor.fetchone()[0]

    if total == 0:
        conn.close()
        return []

    cursor.execute(
        """
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    raw_pcts = []
    for row in rows:
        pct = round((row["total"] / total) * 100)
        raw_pcts.append(pct)

    # Adjust to sum to exactly 100
    remainder = 100 - sum(raw_pcts)
    if remainder != 0 and raw_pcts:
        raw_pcts[0] += remainder

    breakdown = []
    for i, row in enumerate(rows):
        breakdown.append({
            "name": row["category"],
            "amount": _format_inr(row["total"]),
            "pct": raw_pcts[i],
            "cls": _category_cls(row["category"]),
        })

    return breakdown
