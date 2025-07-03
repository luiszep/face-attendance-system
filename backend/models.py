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
    Represents a student entry in the system.

    Attributes:
        id (int): Primary key.
        name (str): Student's name (unique).
        rollno (str): Roll number (unique).
        division (str): Academic division or section.
        branch (str): Academic branch or department.
        regid (str): Registration ID (unique; used for encoding and attendance).
        session_code_id (int): Foreign key linking the student to a SessionCode (business context).
    """
    __tablename__ = 'student_data'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    rollno = db.Column(db.String(120), unique=True, nullable=False)
    division = db.Column(db.String(80), nullable=False)
    branch = db.Column(db.String(80), nullable=False)
    regid = db.Column(db.String(80), unique=True, nullable=False)
    session_code_id = db.Column(db.Integer, nullable=False)


# -------------------------------
# Model: Attendance
# -------------------------------
class Attendance(db.Model):
    """
    Represents a single attendance entry for a student.

    Attributes:
        id (int): Primary key.
        name (str): Student's name.
        start_time (str): Time when the student first appeared.
        end_time (str): Time when the student last appeared.
        date (date): Date of the attendance record.
        roll_no (str): Student's roll number.
        division (str): Academic division or section.
        branch (str): Academic branch or department.
        reg_id (str): Registration ID (links back to student identity).
        session_code_id (int): Foreign key linking to the SessionCode (business context).
    """
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    date = db.Column(db.Date, default=datetime.date.today)
    roll_no = db.Column(db.String(20), nullable=False)
    division = db.Column(db.String(10))
    branch = db.Column(db.String(100))
    reg_id = db.Column(db.String(100))
    session_code_id = db.Column(db.Integer, nullable=False)

    # Ensures that a student can have only one record per date
    __table_args__ = (
        db.UniqueConstraint('name', 'date', name='uix_name_date'),
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
    username = db.Column(db.String(20), nullable=False)
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
