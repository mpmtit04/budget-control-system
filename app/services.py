import os
import pandas as pd
from werkzeug.utils import secure_filename
from flask_mail import Message

from app import db, mail
from app.models import Budget

ALLOWED_EXTENSIONS = {"xls", "xlsx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage, upload_folder):
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    filepath = os.path.join(upload_folder, filename)
    file_storage.save(filepath)
    return filepath, filename

def _clean_columns(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df

def _pick_value(row, candidates, default=None):
    for col in candidates:
        if col in row.index and pd.notna(row[col]):
            return row[col]
    return default

def _safe_float(value, default=0):
    if value is None:
        return default

    text = str(value).strip().replace(",", "")
    if text == "":
        return default

    try:
        return float(text)
    except ValueError:
        return None

def _safe_int(value, default=0):
    num = _safe_float(value, None)
    if num is None:
        return default
    return int(num)

def import_budget_excel(filepath):
    df = pd.read_excel(filepath)
    df = _clean_columns(df)

    required_any = {
        "department": ["Department", "Dept", "ฝ่าย", "แผนก"],
        "category": ["Category", "Budget Category", "หมวด", "ประเภทงบ"],
        "project": ["Project", "Project Name", "โครงการ", "รายการ"],
        "amount": ["Budget", "Amount", "งบประมาณ", "Budget Amount"],
        "fiscal_year": ["Year", "Fiscal Year", "ปี", "ปีงบประมาณ"],
    }

    missing = []
    for key, options in required_any.items():
        if not any(col in df.columns for col in options):
            missing.append(f"{key}: {', '.join(options)}")

    if missing:
        raise ValueError("ไม่พบคอลัมน์ที่จำเป็น -> " + " | ".join(missing))

    created = 0
    skipped = 0

    for _, row in df.iterrows():
        department = _pick_value(row, required_any["department"], "")
        category = _pick_value(row, required_any["category"], "")
        project = _pick_value(row, required_any["project"], "")
        amount_raw = _pick_value(row, required_any["amount"], 0)
        fiscal_year_raw = _pick_value(row, required_any["fiscal_year"], 0)

        project_text = str(project).strip()
        if project_text == "":
            skipped += 1
            continue

        amount = _safe_float(amount_raw, None)
        if amount is None:
            skipped += 1
            continue

        fiscal_year = _safe_int(fiscal_year_raw, 0)

        budget = Budget(
            department=str(department).strip(),
            category=str(category).strip(),
            project=project_text,
            amount=amount,
            used_amount=0,
            fiscal_year=fiscal_year,
            owner=str(_pick_value(row, ["Owner", "Responsible", "ผู้รับผิดชอบ"], "")).strip() or None,
            budget_code=str(_pick_value(row, ["Budget Code", "Code", "รหัสงบ"], "")).strip() or None,
            remark=str(_pick_value(row, ["Remark", "Note", "หมายเหตุ"], "")).strip() or None,
        )
        db.session.add(budget)
        created += 1

    db.session.commit()
    return created, skipped

def export_budgets_to_excel(filepath, budgets):
    rows = []
    for item in budgets:
        rows.append({
            "ID": item.id,
            "Department": item.department,
            "Category": item.category,
            "Project": item.project,
            "Budget Code": item.budget_code,
            "Amount": item.amount,
            "Used Amount": item.used_amount,
            "Balance": item.balance_amount,
            "Fiscal Year": item.fiscal_year,
            "Owner": item.owner,
            "Remark": item.remark,
        })

    df = pd.DataFrame(rows)
    df.to_excel(filepath, index=False, engine="xlsxwriter")
    return filepath

def send_email_alert(subject, recipients, body):
    if not recipients:
        return False, "no recipients"

    try:
        msg = Message(subject=subject, recipients=recipients, body=body)
        mail.send(msg)
        return True, "sent"
    except Exception as e:
        return False, str(e)