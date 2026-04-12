# Spec: Registration

## Overview

Implement user registration for Spendly. New users can create an account by providing their name, email, and password. The account is stored in SQLite with a hashed password, and duplicate email addresses are rejected with a clear error message.

---

## Depends on

- Step 1 (Database Setup) — users table must exist

---

## Routes

- `GET /register` — render registration form — public
- `POST /register` — create user account, redirect to login on success — public

---

## Database changes

No new tables or columns. Uses existing `users` table from Step 1.

---

## Templates

- **Create:** none
- **Modify:** `templates/register.html` — add `method="POST"`, handle `POST` with redirect/error logic

---

## Files to change

- `app.py` — implement POST handler for `/register`
- `templates/register.html` — update form to support POST (already has `action="/register"`)

---

## Files to create

- `database/db.py` — add `add_user()` function (new helper in existing file)

---

## New dependencies

No new pip packages. Use `werkzeug.security.generate_password_hash` (already in requirements.txt).

---

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterized queries only (`?` placeholders)
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.py` route functions fetch data and render template only — DB logic goes in `database/db.py`

---

## Definition of done

- [ ] `GET /register` renders the registration form
- [ ] `POST /register` with valid data creates a user and redirects to `/login`
- [ ] `POST /register` with a duplicate email re-renders the form with an error message
- [ ] Password is stored as a hash, never plaintext
- [ ] New user can log in with the registered email and password
- [ ] `add_user()` function exists in `database/db.py` and uses parameterized SQL
