import os

class Config:
    SECRET_KEY = "budget-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///budget.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "uploads"