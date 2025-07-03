import cv2
import face_recognition
import numpy as np
from datetime import datetime

# --- Allowed file extensions for uploads ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- Check if the uploaded file has an allowed extension ---
def allowed_file(filename):
    """
    Check if the uploaded file has an allowed image extension.
    Args:
        filename (str): The name of the uploaded file.
    Returns:
        bool: True if the file has an allowed extension, False otherwise.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Encode known student images ---
def findEncodings(imageslist):
    """
    Generate face encodings for a list of student images.
    Args:
        imageslist (list): List of images (as NumPy arrays).
    Returns:
        list: List of 128-dimension face encodings.
    """
    encodeList = []
    for img in imageslist:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert image to RGB (required by face_recognition)
        encode = face_recognition.face_encodings(img)[0]  # Get encoding for the first detected face
        encodeList.append(encode)
    return encodeList

# --- Compare incoming face with known encodings ---
def compare(encodeListKnown, encodeFace):
    """
    Compare an unknown face encoding with a list of known encodings.
    Args:
        encodeListKnown (list): Known face encodings.
        encodeFace (list): Encoding of the detected face.
    Returns:
        tuple:
            matches (list of bool): Whether each known encoding matches the input face.
            faceDis (list of float): Distances between known encodings and input.
            matchIndex (int): Index of the best match (lowest distance).
    """
    matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
    faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
    matchIndex = np.argmin(faceDis)  # Index of best match
    return matches, faceDis, matchIndex

# --- Get student ID from a successful match ---
def get_data(matches, matchIndex, studentIds):
    """
    Retrieve student ID if a valid face match is found.
    Args:
        matches (list): Boolean list indicating match status.
        matchIndex (int): Index of the closest match.
        studentIds (list): List of student IDs corresponding to known encodings.
    Returns:
        str or None: The matched student ID or None if no valid match.
    """
    if matches[matchIndex]:
        return studentIds[matchIndex]
    return None

# --- Retrieve student information from the database ---
def mysqlconnect(student_id, session_code_id):
    """
    Fetch detailed student information from the database 
    based on student ID and session code.
    Args:
        student_id (str): The recognized student's ID.
        session_code_id (int): The associated session code.
    Returns:
        tuple: (id, name, rollno, division, branch) if found,
               otherwise (None, None, None, None, None).
    """
    from backend.app import app
    from backend.models import Student_data
    if student_id is None:
        return None, None, None, None, None
    try:
        with app.app_context():
            student_data = Student_data.query.filter_by(
                regid=student_id,
                session_code_id=session_code_id
            ).first()
            if student_data:
                return (
                    student_data.id,
                    student_data.name,
                    student_data.rollno,
                    student_data.division,
                    student_data.branch
                )
            else:
                return None, None, None, None, None
    except Exception as e:
        print("Error fetching student data:", e)
        return None, None, None, None, None

# --- Record or update attendance entry ---
def record_attendance(name, current_date, roll_no, div, branch, reg_id, session_code_id):
    """
    Record a new attendance entry or update the existing one for the student on the current date.
    Args:
        name (str): Student's full name.
        current_date (date): The date of attendance.
        roll_no (str): Student's roll number.
        div (str): Division or class section.
        branch (str): Student's academic branch.
        reg_id (str): Unique registration ID of the student.
        session_code_id (int): ID of the active session code.
    """
    from backend.app import app
    from backend.models import db, Attendance
    try:
        with app.app_context():
            # Check if an attendance entry already exists for this student on this date/session
            existing_entry = Attendance.query.filter_by(
                reg_id=reg_id,
                date=current_date,
                session_code_id=session_code_id
            ).first()
            current_time_str = datetime.now().strftime("%H:%M:%S")
            if existing_entry:
                # Update end time if entry exists
                existing_entry.end_time = current_time_str
                db.session.commit()
                print("Attendance end time updated.")
            else:
                # Create a new attendance record
                new_attendance = Attendance(
                    name=name,
                    start_time=current_time_str,
                    end_time=current_time_str,
                    date=current_date,
                    roll_no=roll_no,
                    division=div,
                    branch=branch,
                    reg_id=reg_id,
                    session_code_id=session_code_id
                )
                db.session.add(new_attendance)
                db.session.commit()
                print(f"Attendance recorded for {reg_id} in session {session_code_id}.")
                print("Start and end time initialized (first entry).")
    except Exception as e:
        print(f"[ERROR] Failed to record attendance: {e}")
