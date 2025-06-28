from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

# Models used to connect in SQL Alchemy
# Model of students data table
class Student_data(db.Model):
    __tablename__ = 'student_data'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    rollno = db.Column(db.String(120), unique=True, nullable=False)
    division = db.Column(db.String(80), nullable=False)
    branch = db.Column(db.String(80), nullable=False)
    regid = db.Column(db.String(80), unique=True, nullable=False)

    # Foreign key to link to session codes
    session_code_id = db.Column(db.Integer, db.ForeignKey('session_code.id'), nullable=False)

    


# Model of Attendance table
class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    date = db.Column(db.Date, default=datetime.date.today)
    roll_no = db.Column(db.String(20), nullable=False, unique=False)
    division = db.Column(db.String(10))
    branch = db.Column(db.String(100))
    reg_id = db.Column(db.String(100))

    # Foreign key to link to session codes
    session_code_id = db.Column(db.Integer, db.ForeignKey('session_code.id'), nullable=False)

    __table_args__ = (
    db.UniqueConstraint('name', 'date', name='uix_name_date'),
    )


# Model of users table
class Users(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    reg_id = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20))

    # Foreign key to link to session codes
    session_code_id = db.Column(db.Integer, db.ForeignKey('session_code.id'), nullable=False)


    def __repr__(self):
        return f'<User: {self.username}, Role: {self.role}>'

    def get_id(self):
        return str(self.id)
    

# Model of session codes table
class SessionCode(db.Model):
    __tablename__ = 'session_code'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'school-abc-123'
    business_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
