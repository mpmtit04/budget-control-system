from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))


class Budget(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100))
    category = db.Column(db.String(100))
    project = db.Column(db.String(200))
    amount = db.Column(db.Float)
    used = db.Column(db.Float)
    year = db.Column(db.Integer)


class Contract(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(200))
    contract_name = db.Column(db.String(200))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    amount = db.Column(db.Float)