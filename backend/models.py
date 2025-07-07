from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import datetime

# Initialize SQLAlchemy instance
db = SQLAlchemy()


# -------------------------------
# Model: Student_data
# -------------------------------
class Student_data(db.Model):
    """
    Represents an employee entry in the system.

    Attributes:
        id (int): Primary key.
        first_name (str): First name of the employee.
        last_name (str): Last name of the employee.
        occupation (str): Job title or role.
        regular_wage (float): Hourly rate for regular working hours.
        overtime_wage (float): Hourly rate for overtime work.
        regular_hours (int): Daily max hours before overtime applies.
        maximum_overtime_hours (int, optional): Cap on daily overtime hours (nullable).
        regid (str): Registration ID (used for facial recognition mapping).
        session_code_id (int): Business or organization context (foreign key).
    """
    __tablename__ = 'student_data'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    occupation = db.Column(db.String(80), nullable=False)
    regular_wage = db.Column(db.Float, nullable=False)
    overtime_wage = db.Column(db.Float, nullable=False)
    regular_hours = db.Column(db.Integer, nullable=False)
    maximum_overtime_hours = db.Column(db.Integer, nullable=True)
    regid = db.Column(db.String(80), nullable=False)
    session_code_id = db.Column(db.Integer, nullable=False)

    __table_args__ = (
    db.UniqueConstraint('regid', 'session_code_id', name='uq_regid_per_session'),
    )


# -------------------------------
# Model: Attendance
# -------------------------------
class Attendance(db.Model):
    """
    Represents a single attendance entry for a student.

    Attributes:
        id (int): Primary key.
        first_name (str): First name of the employee.
        last_name (str): Last name of the employee.
        occupation (str): Job title or role.
        regular_wage (float): Hourly wage at the time of attendance.        
        start_time (str): Time when the student first appeared.
        end_time (str): Time when the student last appeared.
        date (date): Date of the attendance record.
        reg_id (str): Registration ID (links back to student identity).
        session_code_id (int): Foreign key linking to the SessionCode (business context).
    """
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    date = db.Column(db.Date, default=datetime.date.today)
    regular_wage = db.Column(db.Float, nullable=False)
    occupation = db.Column(db.String(80), nullable=False)
    reg_id = db.Column(db.String(100))
    session_code_id = db.Column(db.Integer, nullable=False)

    # Ensures that a student can have only one record per date
    __table_args__ = (
        db.UniqueConstraint('reg_id', 'date', 'session_code_id', name='uix_regid_date_session'),
    )


# -------------------------------
# Model: Users
# -------------------------------
class Users(db.Model, UserMixin):
    """
    Represents a user in the system. Inherits from UserMixin for Flask-Login integration.

    Attributes:
        id (int): Primary key.
        username (str): Login username.
        password (str): Hashed user password.
        reg_id (str): Registration ID associated with the user.
        role (str): Role of the user (e.g., admin, teacher, student).
        session_code_id (int): Foreign key linking to a specific SessionCode (business).
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    reg_id = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20))
    session_code_id = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<User: {self.username}, Role: {self.role}>'

    def get_id(self):
        """Override required by Flask-Login to return user ID as a string."""
        return str(self.id)

    
# -------------------------------
# Model: SessionCode
# -------------------------------
class SessionCode(db.Model):
    """
    Represents a unique session code used to associate users, students, and attendance
    with a specific business or organization.

    Attributes:
        id (int): Primary key.
        code (str): Unique session code (e.g., 'school-abc-123').
        business_name (str): Name of the associated business or organization.
        created_at (datetime): Timestamp of when the session was created.
    """
    __tablename__ = 'session_code'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'school-abc-123'
    business_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
