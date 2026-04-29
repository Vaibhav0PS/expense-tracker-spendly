from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, session, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.config["SECRET_KEY"] = "spendly-secret-key-change-in-production"

with app.app_context():
    init_db()
    seed_db()


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return {"current_user": None}

    from database.db import get_user_by_id
    return {"current_user": get_user_by_id(user_id)}


def initials_for_name(name):
    parts = name.split()
    if not parts:
        return "U"
    return "".join(part[0].upper() for part in parts[:2])


def format_member_since(created_at):
    if not created_at:
        return "Recently"

    try:
        joined_at = datetime.fromisoformat(created_at)
    except ValueError:
        return "Recently"

    return joined_at.strftime("%B %Y")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    from database.db import add_user
    user_id = add_user(name, email, password)

    if user_id is None:
        return render_template("register.html", error="An account with this email already exists.")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"].strip().lower()
    password = request.form["password"]

    from database.db import get_user_by_email
    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    return redirect(url_for("landing"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    from database.queries import get_user_profile, get_summary_stats, get_recent_transactions, get_category_breakdown

    user = get_user_profile(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    # ── Date filter handling ──────────────────────────────────────────
    raw_from = request.args.get("date_from")
    raw_to   = request.args.get("date_to")

    date_from, date_to = None, None

    if raw_from:
        try:
            datetime.strptime(raw_from, "%Y-%m-%d")
            date_from = raw_from
        except ValueError:
            pass

    if raw_to:
        try:
            datetime.strptime(raw_to, "%Y-%m-%d")
            date_to = raw_to
        except ValueError:
            pass

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.")
        date_from, date_to = None, None

    # ── Compute preset ranges ─────────────────────────────────────────
    now = datetime.now()

    this_month_from = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
    this_month_to   = now.strftime("%Y-%m-%d")

    # last_N_months: current calendar month plus previous N-1 months.
    def months_ago(n):
        m = now.month - n
        y = now.year + m // 12
        m = m % 12
        if m < 1:
            m += 12
            y -= 1
        return datetime(y, m, 1).strftime("%Y-%m-%d")

    last_3_from = months_ago(3)
    last_3_to   = now.strftime("%Y-%m-%d")

    last_6_from = months_ago(6)
    last_6_to   = now.strftime("%Y-%m-%d")

    # ── Determine active preset ───────────────────────────────────────
    if date_from is None and date_to is None:
        active_preset = "all_time"
    elif date_from == this_month_from and date_to == this_month_to:
        active_preset = "this_month"
    elif date_from == last_3_from and date_to == last_3_to:
        active_preset = "last_3_months"
    elif date_from == last_6_from and date_to == last_6_to:
        active_preset = "last_6_months"
    else:
        active_preset = "custom"

    # ── Query data ───────────────────────────────────────────────────
    summary = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(user_id, limit=10, date_from=date_from, date_to=date_to)
    categories = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)

    # Map summary keys to what the template expects
    stats = {
        "account_balance": summary["total_spent"],
        "monthly_spending": summary["monthly_spending"],
        "total_expenses": summary["transaction_count"],
        "top_category": summary["top_category"],
    }

    return render_template(
        "profile.html",
        user=user, stats=stats,
        transactions=transactions, categories=categories,
        filter_active=(date_from is not None),
        active_preset=active_preset,
        date_from_value=date_from or "",
        date_to_value=date_to or "",
        preset_this_month=(this_month_from, this_month_to),
        preset_last_3_months=(last_3_from, last_3_to),
        preset_last_6_months=(last_6_from, last_6_to),
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
