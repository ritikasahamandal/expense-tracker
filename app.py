from flask import Flask, render_template, request, url_for, make_response, flash, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime, date as dt_date
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "super-secret-key"

app.config['SQLALCHEMY_DATABASE_URI']= 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']= False
db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    description= db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable =False)
    category =db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)


with app.app_context():
    db.create_all()

CATEGORIES=['Food','Transport','Rent','Utilities','Health']

def parse_date_or_none(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.route("/")
def index():
    # 1 read query string
    start_str = (request.args.get("start") or "").strip()
    end_str = request.args.get("end", "").strip()
    selected_category= (request.args.get("category") or "").strip()

    # 2 parsing

    start_date= parse_date_or_none(start_str)
    end_date= parse_date_or_none(end_str)

    if start_date and end_date and end_date< start_date:
        flash("End date cannot be before start date","error")
        start_date=end_date=None
        start_str=end_str=""
        
        q = Expense.query

        if start_date:
            q=q.filter(Expense.date>= start_date)
        if end_date:
            q= q.filter(Expense.date>=start_date)
        if selected_category:
            q=q.filter(Expense.category == selected_category)

    expense =Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total=round(sum(e.amount for e in expense),2)

    cat_q= db.session.query(Expense.category, func.sum(Expense.amount))

    if start_date:
        cat_q= cat_q.filter(Expense.date >= start_date)
    if end_date:
        cat_q=cat_q.filter(Expense.date <= end_date)
    if selected_category:
        cat_q=cat_q.filter(Expense.category == selected_category)

    cat_rows= cat_q.group_by(Expense.category).all()
    print(cat_rows)
    cat_labels=[c for c, _ in cat_rows]
    cat_values=[round(float(s or 0), 2) for _, s in cat_rows]
    # print(cat_values)


    day_q= db.session.query(Expense.category, func.sum(Expense.amount))

    if start_date:
        day_q= day_q.filter(Expense.date >= start_date)
    if end_date:
        day_q=day_q.filter(Expense.date <= end_date)
    if selected_category:
        day_q=day_q.filter(Expense.category == selected_category)

    day_rows= day_q.group_by(Expense.category).order_by(Expense.date).all()
    # print(cat_rows)
    day_labels=[d.format() for d, _ in day_rows]
    day_values=[round(float(s or 0), 2) for _, s in day_rows]

    return render_template("index.html",
                           

                           
                           categories=CATEGORIES,
                           today=date.today().isoformat(),
                            expense=expense,
                            total=total,
                            start_date=start_date,
                            end_date=end_date,
                            selected_category= selected_category,
                            cat_labels= cat_labels,
                            cat_values= cat_values,
                            day_labels=day_labels,
                            day_values=day_values
                            
                            )

@app.route("/add", methods=['POST'])
def add():

    description= (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category=(request.form.get("category") or "").strip()
    date_str=(request.form.get("date") or "").strip()


    if not description or not amount_str or not category:
        flash("Please fill description, amount amd category", "error")


    try:
        amount = float(amount_str)
        if amount <=0:
            raise ValueError
        
    except ValueError:
        flash("Amount must be positive number", "error")
        return redirect(url_for("index"))


    try:
        d= datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        d=date.today
    e= Expense(description=description, amount=amount, category=category, date=d)
    db.session.add(e)
    db.session.commit()

    flash("Expense added","success")
    return redirect(url_for("index"))

@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete(expense_id):
    e= Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted","success")
    return redirect(url_for("index"))


@app.route('/edit/<int:expense_id>', methods=['GET'])
def edit(expense_id):
    e = Expense.query.get_or_404(expense_id)

    return render_template(
        "edit.html",
        expense=e,
        categories=CATEGORIES,
        today=dt_date.today().isoformat()
    )


@app.route('/edit/<int:expense_id>', methods=['POST'])
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


@app.route("/export.csv")
def export_csv():
    # 1 read query string
    start_str = (request.args.get("start") or "").strip()
    end_str = request.args.get("end", "").strip()
    selected_category= (request.args.get("category") or "").strip()

    # 2 parsing

    start_date= parse_date_or_none(start_str)
    end_date= parse_date_or_none(end_str)

    q = Expense.query

    if start_date:
            q=q.filter(Expense.date>= start_date)
    if end_date:
            q= q.filter(Expense.date>=start_date)
    if selected_category:
            q=q.filter(Expense.category == selected_category)

    expenses = q.order_by(Expense.date, Expense.id).all()

    lines = ["date, description, category, amount"]

    for e in expenses:
        lines.append(f"{e.date.isoformat()},{e.description}, {e.category},{e.amount:.2f}")
    csv_data="\n".join(lines)

    fname_start= start_str or "all"
    fname_end=end_str or "all"
    filename= f"expenses_{fname_start}_to_{fname_end}.csv"

    return Response(
        csv_data,
        headers={
            "Content-Type":"text/csv",
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )




if __name__== "__main__":
    app.run(debug=True)