from flask import Blueprint, render_template, request, redirect
from .models import Budget, Contract
from . import db
import pandas as pd

main = Blueprint("main", __name__)


@main.route("/")
def dashboard():

    budgets = Budget.query.all()
    contracts = Contract.query.all()

    return render_template(
        "dashboard.html",
        budgets=budgets,
        contracts=contracts
    )


@main.route("/budget/new", methods=["GET", "POST"])
def new_budget():

    if request.method == "POST":

        budget = Budget(
            department=request.form["department"],
            category=request.form["category"],
            project=request.form["project"],
            amount=request.form["amount"],
            used=0,
            year=request.form["year"]
        )

        db.session.add(budget)
        db.session.commit()

        return redirect("/")

    return render_template("budget_form.html")


@main.route("/upload", methods=["GET", "POST"])
def upload_excel():

    if request.method == "POST":

        file = request.files["file"]

        df = pd.read_excel(file)

        for _, row in df.iterrows():

            budget = Budget(
                department=row["Department"],
                category=row["Category"],
                project=row["Project"],
                amount=row["Budget"],
                used=0,
                year=row["Year"]
            )

            db.session.add(budget)

        db.session.commit()

        return redirect("/")

    return render_template("upload.html")