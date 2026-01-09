from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, Response
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import date, datetime, date as dt_date

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = "super-secret-key"

# ---------------- DATABASE (SQLite ONLY) ----------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- AUTO CREATE TABLES (NO SHELL NEEDED) ----------------
@app.before_request
def create_tables_once():
    if not hasattr(app, "_tables_created"):
        db.create_all()
        app._tables_created = True

# ---------------- MODEL ----------------
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

# ---------------- CONSTANTS ----------------
CATEGORIES = ["Food", "Transport", "Rent", "Utilities", "Health"]

# ---------------- HELPERS ----------------
def parse_date_or_none(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = (request.args.get("category") or "").strip()

    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    if start_date and end_date and end_date < start_date:
        flash("End date cannot be before start date", "error")
        start_date = end_date = None

    # Base query
    q = Expense.query

    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)
    if selected_category:
        q = q.filter(Expense.category == selected_category)

    expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = round(sum(e.amount for e in expenses), 2)

    # Category-wise totals
    cat_rows = (
        db.session.query(
            Expense.category,
            func.sum(Expense.amount)
        )
        .filter(q.whereclause)
        .group_by(Expense.category)
        .all()
    )

    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(s or 0), 2) for _, s in cat_rows]

    # Spending over time (DATE-WISE)
    day_rows = (
        db.session.query(
            Expense.date,
            func.sum(Expense.amount)
        )
        .filter(q.whereclause)
        .group_by(Expense.date)
        .order_by(Expense.date)
        .all()
    )

    day_labels = [d.isoformat() for d, _ in day_rows]
    day_values = [round(float(s or 0), 2) for _, s in day_rows]

    return render_template(
        "index.html",
        categories=CATEGORIES,
        today=date.today().isoformat(),
        expense=expenses,
        total=total,
        start_date=start_date,
        end_date=end_date,
        selected_category=selected_category,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values
    )

# ---------------- ADD EXPENSE ----------------
@app.route("/add", methods=["POST"])
def add():
    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not description or not amount_str or not category:
        flash("Please fill all required fields", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Amount must be a positive number", "error")
        return redirect(url_for("index"))

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        d = date.today()

    e = Expense(
        description=description,
        amount=amount,
        category=category,
        date=d
    )

    db.session.add(e)
    db.session.commit()

    flash("Expense added successfully", "success")
    return redirect(url_for("index"))

# ---------------- DELETE ----------------
@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "success")
    return redirect(url_for("index"))

# ---------------- EDIT ----------------
@app.route("/edit/<int:expense_id>", methods=["GET"])
def edit(expense_id):
    e = Expense.query.get_or_404(expense_id)
    return render_template(
        "edit.html",
        expense=e,
        categories=CATEGORIES,
        today=dt_date.today().isoformat()
    )

@app.route("/edit/<int:expense_id>", methods=["POST"])
def edit_post(expense_id):
    e = Expense.query.get_or_404(expense_id)

    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not description or not amount_str or not category:
        flash("Please fill all details", "error")
        return redirect(url_for("edit", expense_id=e.id))

    e.description = description
    e.amount = float(amount_str)
    e.category = category
    e.date = dt_date.fromisoformat(date_str) if date_str else e.date

    db.session.commit()
    flash("Expense updated successfully", "success")
    return redirect(url_for("index"))

# ---------------- EXPORT CSV ----------------
@app.route("/export.csv")
def export_csv():
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = (request.args.get("category") or "").strip()

    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    q = Expense.query

    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)
    if selected_category:
        q = q.filter(Expense.category == selected_category)

    expenses = q.order_by(Expense.date, Expense.id).all()

    lines = ["date,description,category,amount"]
    for e in expenses:
        lines.append(
            f"{e.date.isoformat()},{e.description},{e.category},{e.amount:.2f}"
        )

    csv_data = "\n".join(lines)

    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment; filename=expenses.csv"
        }
    )

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
