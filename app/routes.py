from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User, Budget, Contract
from app.services import allowed_file, save_upload, import_budget_excel

main = Blueprint("main", __name__)

@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash("เข้าสู่ระบบสำเร็จ", "success")
            return redirect(url_for("main.dashboard"))

        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "danger")

    return render_template("login.html")

@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ออกจากระบบแล้ว", "info")
    return redirect(url_for("main.login"))

@main.route("/")
@login_required
def dashboard():
    budgets = Budget.query.order_by(Budget.id.desc()).limit(5).all()
    contracts = Contract.query.order_by(Contract.end_date.asc()).limit(5).all()

    total_budget = sum(b.amount or 0 for b in Budget.query.all())
    total_used = sum(b.used_amount or 0 for b in Budget.query.all())
    total_balance = total_budget - total_used

    expiring_contracts = Contract.query.all()
    expiring_contracts = [c for c in expiring_contracts if c.days_to_expire <= c.alert_days]

    return render_template(
        "dashboard.html",
        budgets=budgets,
        contracts=contracts,
        total_budget=total_budget,
        total_used=total_used,
        total_balance=total_balance,
        expiring_count=len(expiring_contracts),
    )

@main.route("/budgets")
@login_required
def budgets():
    items = Budget.query.order_by(Budget.id.desc()).all()
    return render_template("budgets.html", items=items)

@main.route("/budget/new", methods=["GET", "POST"])
@login_required
def new_budget():
    if request.method == "POST":
        budget = Budget(
            department=request.form.get("department", "").strip(),
            category=request.form.get("category", "").strip(),
            project=request.form.get("project", "").strip(),
            budget_code=request.form.get("budget_code", "").strip(),
            amount=float(request.form.get("amount", 0) or 0),
            used_amount=float(request.form.get("used_amount", 0) or 0),
            fiscal_year=int(request.form.get("fiscal_year", 0) or 0),
            owner=request.form.get("owner", "").strip(),
            remark=request.form.get("remark", "").strip(),
        )
        db.session.add(budget)
        db.session.commit()
        flash("เพิ่มงบประมาณเรียบร้อย", "success")
        return redirect(url_for("main.budgets"))

    return render_template("budget_form.html")

@main.route("/contracts", methods=["GET", "POST"])
@login_required
def contracts():
    if request.method == "POST":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

        contract = Contract(
            vendor=request.form.get("vendor", "").strip(),
            contract_name=request.form.get("contract_name", "").strip(),
            contract_no=request.form.get("contract_no", "").strip(),
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            amount=float(request.form.get("amount", 0) or 0),
            alert_days=int(request.form.get("alert_days", 30) or 30),
            status=request.form.get("status", "Active")
        )
        db.session.add(contract)
        db.session.commit()
        flash("เพิ่มสัญญาเรียบร้อย", "success")
        return redirect(url_for("main.contracts"))

    items = Contract.query.order_by(Contract.end_date.asc()).all()
    return render_template("contracts.html", items=items)

@main.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("กรุณาเลือกไฟล์ Excel", "warning")
            return redirect(url_for("main.upload"))

        if not allowed_file(file.filename):
            flash("รองรับเฉพาะไฟล์ .xls และ .xlsx", "danger")
            return redirect(url_for("main.upload"))

        filepath, _ = save_upload(file, upload_folder="uploads")

        try:
            created = import_budget_excel(filepath)
            flash(f"นำเข้าข้อมูลสำเร็จ {created} รายการ", "success")
        except Exception as e:
            flash(f"เกิดข้อผิดพลาดในการ import: {e}", "danger")

        return redirect(url_for("main.budgets"))

    return render_template("upload.html")