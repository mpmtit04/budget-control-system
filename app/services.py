import os
import pandas as pd
from werkzeug.utils import secure_filename

from app import db
from app.models import Budget

ALLOWED_EXTENSIONS = {"xls", "xlsx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage, upload_folder):
    filename = secure_filename(file_storage.filename)
    filepath = os.path.join(upload_folder, filename)
    file_storage.save(filepath)
    return filepath, filename

def import_budget_excel(filepath):
    df = pd.read_excel(filepath)
    df.columns = [str(col).strip() for col in df.columns]

    column_map = {
        "Department": "department",
        "Category": "category",
        "Project": "project",
        "Budget": "amount",
        "Year": "fiscal_year",
        "Owner": "owner",
        "Budget Code": "budget_code",
        "Remark": "remark",
    }

    created = 0

    required_columns = ["Department", "Category", "Project", "Budget", "Year"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"ไม่พบคอลัมน์ที่จำเป็น: {col}")

    for _, row in df.iterrows():
        budget = Budget(
            department=str(row.get("Department", "")).strip(),
            category=str(row.get("Category", "")).strip(),
            project=str(row.get("Project", "")).strip(),
            amount=float(row.get("Budget", 0) or 0),
            used_amount=0,
            fiscal_year=int(row.get("Year", 0) or 0),
            owner=str(row.get("Owner", "")).strip() if "Owner" in df.columns else None,
            budget_code=str(row.get("Budget Code", "")).strip() if "Budget Code" in df.columns else None,
            remark=str(row.get("Remark", "")).strip() if "Remark" in df.columns else None,
        )
        db.session.add(budget)
        created += 1

    db.session.commit()
    return created