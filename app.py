from flask import Flask, render_template, redirect, url_for, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.config["SECRET_KEY"] = "spendly-secret-key-change-in-production"

with app.app_context():
    init_db()
    seed_db()


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
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Priya Sharma",
        "email": "priya.sharma@gmail.com",
        "member_since": "September 2024",
        "avatar_initials": "PS"
    }

    stats = {
        "account_balance": "\u20b91,24,580",
        "monthly_spending": "\u20b918,420",
        "total_expenses": 47,
        "top_category": "Food & Dining"
    }

    transactions = [
        {"id": 1,  "date": "17 Apr 2026", "desc": "Zomato \u2014 dinner",             "category": "Food & Dining",    "cls": "food",         "amount": "-\u20b9820"},
        {"id": 2,  "date": "16 Apr 2026", "desc": "Metro \u2014上班",                 "category": "Transport",        "cls": "transport",    "amount": "-\u20b960"},
        {"id": 3,  "date": "15 Apr 2026", "desc": "Amazon \u2014 earbuds",            "category": "Shopping",         "cls": "shopping",     "amount": "-\u20b93,499"},
        {"id": 4,  "date": "14 Apr 2026", "desc": "Netflix subscription",             "category": "Entertainment",    "cls": "entertainment","amount": "-\u20b9199"},
        {"id": 5,  "date": "13 Apr 2026", "desc": "Reliance Fresh \u2014 groceries",  "category": "Food & Dining",    "cls": "food",         "amount": "-\u20b91,240"},
        {"id": 6,  "date": "12 Apr 2026", "desc": "Bijli bill \u2014 BSES",          "category": "Utilities",        "cls": "utilities",    "amount": "-\u20b91,850"},
        {"id": 7,  "date": "11 Apr 2026", "desc": "Swiggy \u2014 lunch",             "category": "Food & Dining",    "cls": "food",         "amount": "-\u20b9340"},
        {"id": 8,  "date": "10 Apr 2026", "desc": "Metro \u2014上班",                 "category": "Transport",        "cls": "transport",    "amount": "-\u20b960"},
    ]

    categories = [
        {"name": "Food & Dining",    "amount": "\u20b98,240",  "pct": 45, "cls": "food"},
        {"name": "Transport",         "amount": "\u20b93,180",  "pct": 17, "cls": "transport"},
        {"name": "Shopping",          "amount": "\u20b92,899",  "pct": 16, "cls": "shopping"},
        {"name": "Entertainment",     "amount": "\u20b92,100",  "pct": 11, "cls": "entertainment"},
        {"name": "Utilities",         "amount": "\u20b92,001",  "pct": 11, "cls": "utilities"},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories
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
