from datetime import date
from flask_login import UserMixin
from werkzeug.security import check_password_hash
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    role = db.Column(db.String(50), default="Viewer")
    is_active_user = db.Column(db.Boolean, default=True)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(150), nullable=False)
    project = db.Column(db.String(200), nullable=False)
    budget_code = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0)
    used_amount = db.Column(db.Float, nullable=False, default=0)
    fiscal_year = db.Column(db.Integer, nullable=False)
    owner = db.Column(db.String(150), nullable=True)
    remark = db.Column(db.Text, nullable=True)

    @property
    def balance_amount(self):
        return (self.amount or 0) - (self.used_amount or 0)

class Contract(db.Model):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(200), nullable=False)
    contract_name = db.Column(db.String(200), nullable=False)
    contract_no = db.Column(db.String(100), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    alert_days = db.Column(db.Integer, nullable=False, default=30)
    status = db.Column(db.String(50), default="Active")

    @property
    def days_to_expire(self):
        return (self.end_date - date.today()).days