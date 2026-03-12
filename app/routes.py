from datetime import datetime, date
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps

from app import db
from app.models import User, Budget, Contract, BudgetTransaction, ContractRenewal, NotificationLog
from app.services import allowed_file, save_upload, import_budget_excel, export_budgets_to_excel, send_email_alert
from collections import defaultdict

main = Blueprint("main", __name__)

def role_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash("คุณไม่มีสิทธิ์เข้าถึงเมนูนี้", "danger")
                return redirect(url_for("main.dashboard"))
            return func(*args, **kwargs)
        return wrapper
    return decorator

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

    all_budgets = Budget.query.all()
    total_budget = sum(b.amount or 0 for b in all_budgets)
    total_used = sum(b.used_amount or 0 for b in all_budgets)
    total_balance = total_budget - total_used

    expiring_contracts = Contract.query.all()
    expiring_contracts = [c for c in expiring_contracts if c.days_to_expire <= c.alert_days]

    latest_transactions = BudgetTransaction.query.order_by(BudgetTransaction.id.desc()).limit(5).all()

    budget_utilization = 0
    if total_budget > 0:
        budget_utilization = round((total_used / total_budget) * 100, 2)

    return render_template(
        "dashboard.html",
        budgets=budgets,
        contracts=contracts,
        total_budget=total_budget,
        total_used=total_used,
        total_balance=total_balance,
        expiring_count=len(expiring_contracts),
        latest_transactions=latest_transactions,
        budget_utilization=budget_utilization,
    )


@main.route("/api/chart/dashboard")
@login_required
def dashboard_chart_data():
    budgets = Budget.query.all()
    contracts = Contract.query.all()

    # 1) Budget vs Used (Top 10 by used)
    top_budgets = sorted(budgets, key=lambda x: x.used_amount or 0, reverse=True)[:10]
    top10_labels = [b.project for b in top_budgets]
    top10_budget = [b.amount or 0 for b in top_budgets]
    top10_used = [b.used_amount or 0 for b in top_budgets]

    # 2) Budget by Department
    dept_map = defaultdict(float)
    for b in budgets:
        dept_map[b.department or "Unknown"] += b.amount or 0

    dept_labels = list(dept_map.keys())
    dept_budget = list(dept_map.values())

    # 3) Budget by Fiscal Year
    year_map = defaultdict(float)
    year_used_map = defaultdict(float)
    for b in budgets:
        year_map[str(b.fiscal_year)] += b.amount or 0
        year_used_map[str(b.fiscal_year)] += b.used_amount or 0

    year_labels = sorted(year_map.keys())
    year_budget = [year_map[y] for y in year_labels]
    year_used = [year_used_map[y] for y in year_labels]

    # 4) Contract Expiry buckets
    expiry_map = {
        "Expired": 0,
        "0-30 days": 0,
        "31-60 days": 0,
        "61-90 days": 0,
        "90+ days": 0,
    }

    for c in contracts:
        days = c.days_to_expire
        if days < 0:
            expiry_map["Expired"] += 1
        elif days <= 30:
            expiry_map["0-30 days"] += 1
        elif days <= 60:
            expiry_map["31-60 days"] += 1
        elif days <= 90:
            expiry_map["61-90 days"] += 1
        else:
            expiry_map["90+ days"] += 1

    return jsonify({
        "top10": {
            "labels": top10_labels,
            "budget": top10_budget,
            "used": top10_used
        },
        "department": {
            "labels": dept_labels,
            "budget": dept_budget
        },
        "fiscal_year": {
            "labels": year_labels,
            "budget": year_budget,
            "used": year_used
        },
        "contract_expiry": {
            "labels": list(expiry_map.keys()),
            "values": list(expiry_map.values())
        }
    })

@main.route("/budgets")
@login_required
def budgets():
    query = Budget.query

    department = request.args.get("department", "").strip()
    fiscal_year = request.args.get("fiscal_year", "").strip()
    keyword = request.args.get("keyword", "").strip()
    page = request.args.get("page", 1, type=int)

    if department:
        query = query.filter(Budget.department.ilike(f"%{department}%"))
    if fiscal_year:
        try:
            query = query.filter(Budget.fiscal_year == int(fiscal_year))
        except ValueError:
            pass
    if keyword:
        query = query.filter(
            db.or_(
                Budget.project.ilike(f"%{keyword}%"),
                Budget.category.ilike(f"%{keyword}%"),
                Budget.budget_code.ilike(f"%{keyword}%")
            )
        )

    pagination = query.order_by(Budget.id.desc()).paginate(page=page, per_page=10, error_out=False)
    items = pagination.items
    return render_template("budgets.html", items=items, pagination=pagination)

@main.route("/budgets/export")
@login_required
def budgets_export():
    budgets = Budget.query.order_by(Budget.id.desc()).all()

    export_dir = "uploads"
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, "budget_export.xlsx")

    export_budgets_to_excel(filepath, budgets)
    return send_file(filepath, as_attachment=True)

@main.route("/budget/new", methods=["GET", "POST"])
@login_required
@role_required("Admin")
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

@main.route("/budget/<int:budget_id>/transaction", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def budget_transaction(budget_id):
    budget = Budget.query.get_or_404(budget_id)

    if request.method == "POST":
        trans_type = request.form.get("trans_type", "use")
        amount = float(request.form.get("amount", 0) or 0)

        tx = BudgetTransaction(
            budget_id=budget.id,
            trans_date=datetime.strptime(request.form.get("trans_date"), "%Y-%m-%d").date(),
            trans_type=trans_type,
            amount=amount,
            reference_no=request.form.get("reference_no", "").strip(),
            description=request.form.get("description", "").strip(),
            created_by=current_user.full_name
        )
        db.session.add(tx)

        if trans_type == "use":
            budget.used_amount = (budget.used_amount or 0) + amount
        elif trans_type == "adjust_increase":
            budget.amount = (budget.amount or 0) + amount
        elif trans_type == "adjust_decrease":
            budget.amount = (budget.amount or 0) - amount

        db.session.commit()
        flash("บันทึกรายการเรียบร้อย", "success")
        return redirect(url_for("main.budget_transactions", budget_id=budget.id))

    return render_template("budget_transaction_form.html", budget=budget, today=date.today())

@main.route("/budget/<int:budget_id>/transactions")
@login_required
def budget_transactions(budget_id):
    budget = Budget.query.get_or_404(budget_id)
    items = BudgetTransaction.query.filter_by(budget_id=budget.id).order_by(BudgetTransaction.id.desc()).all()
    return render_template("budget_transactions.html", budget=budget, items=items)

@main.route("/contracts", methods=["GET", "POST"])
@login_required
def contracts():
    if request.method == "POST":
        if current_user.role != "Admin":
            flash("คุณไม่มีสิทธิ์เพิ่มสัญญา", "danger")
            return redirect(url_for("main.contracts"))

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

@main.route("/contract/<int:contract_id>/renew", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def contract_renew(contract_id):
    contract = Contract.query.get_or_404(contract_id)

    if request.method == "POST":
        new_end_date = datetime.strptime(request.form.get("new_end_date"), "%Y-%m-%d").date()
        renewal_date = datetime.strptime(request.form.get("renewal_date"), "%Y-%m-%d").date()
        renewal_value = float(request.form.get("renewal_value", 0) or 0)
        remark = request.form.get("remark", "").strip()

        renewal = ContractRenewal(
            contract_id=contract.id,
            old_end_date=contract.end_date,
            new_end_date=new_end_date,
            renewal_date=renewal_date,
            renewal_value=renewal_value,
            remark=remark,
            renewed_by=current_user.full_name
        )
        db.session.add(renewal)

        contract.end_date = new_end_date
        contract.amount = renewal_value if renewal_value > 0 else contract.amount
        contract.status = "Renewed"

        db.session.commit()
        flash("ต่อสัญญาเรียบร้อย", "success")
        return redirect(url_for("main.contracts"))

    return render_template("contract_renew_form.html", contract=contract, today=date.today())

@main.route("/contract/<int:contract_id>/renewals")
@login_required
def contract_renewals(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    items = ContractRenewal.query.filter_by(contract_id=contract.id).order_by(ContractRenewal.id.desc()).all()
    return render_template("contract_renewals.html", contract=contract, items=items)

@main.route("/upload", methods=["GET", "POST"])
@login_required
@role_required("Admin")
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

@main.route("/reports/summary")
@login_required
def report_summary():
    year = request.args.get("year", "").strip()

    query = Budget.query
    if year:
        try:
            query = query.filter(Budget.fiscal_year == int(year))
        except ValueError:
            pass

    budgets = query.all()

    summary = {}
    for b in budgets:
        dept = b.department or "Unknown"
        if dept not in summary:
            summary[dept] = {"budget": 0, "used": 0, "balance": 0}
        summary[dept]["budget"] += b.amount or 0
        summary[dept]["used"] += b.used_amount or 0
        summary[dept]["balance"] += b.balance_amount or 0

    return render_template("report_summary.html", summary=summary, selected_year=year)

@main.route("/alerts/contracts")
@login_required
def contract_alerts():
    items = Contract.query.order_by(Contract.end_date.asc()).all()
    expiring_items = [c for c in items if c.days_to_expire <= c.alert_days]
    return render_template("contract_alerts.html", items=expiring_items)

@main.route("/alerts/contracts/send")
@login_required
@role_required("Admin")
def contract_alerts_send():
    items = Contract.query.order_by(Contract.end_date.asc()).all()
    expiring_items = [c for c in items if c.days_to_expire <= c.alert_days]

    if not current_user.email:
        flash("ผู้ใช้ปัจจุบันยังไม่มี email สำหรับรับแจ้งเตือน", "danger")
        return redirect(url_for("main.contract_alerts"))

    if not expiring_items:
        flash("ไม่มีสัญญาใกล้หมดอายุ", "info")
        return redirect(url_for("main.contract_alerts"))

    lines = ["Contracts ใกล้หมดอายุ:"]
    for c in expiring_items:
        lines.append(f"- {c.contract_name} / {c.vendor} / เหลือ {c.days_to_expire} วัน / สิ้นสุด {c.end_date}")

    body = "\n".join(lines)
    ok, status = send_email_alert(
        subject="Contract Expiry Alert",
        recipients=[current_user.email],
        body=body
    )

    log = NotificationLog(
        notify_type="contract_expiry",
        ref_type="contract_batch",
        ref_id=0,
        recipient=current_user.email,
        channel="email",
        status="sent" if ok else "failed",
        message=body if ok else status
    )
    db.session.add(log)
    db.session.commit()

    if ok:
        flash("ส่ง email แจ้งเตือนแล้ว", "success")
    else:
        flash(f"ส่ง email ไม่สำเร็จ: {status}", "danger")

    return redirect(url_for("main.contract_alerts"))


@main.route("/reports/projects")
@login_required
def report_projects():
    year = request.args.get("year", "").strip()

    query = Budget.query
    if year:
        try:
            query = query.filter(Budget.fiscal_year == int(year))
        except ValueError:
            pass

    items = query.order_by(Budget.fiscal_year.desc(), Budget.project.asc()).all()

    total_budget = sum(x.amount or 0 for x in items)
    total_used = sum(x.used_amount or 0 for x in items)
    total_balance = sum(x.balance_amount or 0 for x in items)

    return render_template(
        "report_projects.html",
        items=items,
        selected_year=year,
        total_budget=total_budget,
        total_used=total_used,
        total_balance=total_balance,
    )

@main.route("/reports/projects-detail")
@login_required
def report_projects_detail():
    year = request.args.get("year", "").strip()

    query = Budget.query
    if year:
        try:
            query = query.filter(Budget.fiscal_year == int(year))
        except ValueError:
            pass

    items = query.order_by(Budget.fiscal_year.desc(), Budget.project.asc()).all()

    total_budget = sum(x.amount or 0 for x in items)
    total_used = sum(x.used_amount or 0 for x in items)
    total_balance = sum((x.amount or 0) - (x.used_amount or 0) for x in items)

    return render_template(
        "report_projects_detail.html",
        items=items,
        selected_year=year,
        total_budget=total_budget,
        total_used=total_used,
        total_balance=total_balance,
    )