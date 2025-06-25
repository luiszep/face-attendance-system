import cv2
import face_recognition
import numpy as np
from datetime import datetime
import time
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

# Function to stop the camera
def stop_camera():
    from app import camera
    if camera is not None:
        camera.release()

# Encode known student images
def findEncodings(imageslist):
    encodeList = []
    for img in imageslist:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encode = face_recognition.face_encodings(img)[0]
        encodeList.append(encode)
    return encodeList

# Compare incoming face with known encodings
def compare(encodeListKnown, encodeFace):
    matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
    faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
    matchIndex = np.argmin(faceDis)
    return matches, faceDis, matchIndex

# Get student ID if match is found
def get_data(matches, matchIndex, studentIds):
    if matches[matchIndex]:
        student_id = studentIds[matchIndex]
        return student_id
    return None

# Get student info from the database by ID
def mysqlconnect(student_id):
    from app import Student_data, app

    if student_id is None:
        return None, None, None, None, None

    try:
        with app.app_context():
            student_data = Student_data.query.filter_by(regid=student_id).first()
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
        print("Error:", e)
        return None, None, None, None, None

# Record or update attendance entry
def record_attendance(name, current_date, roll_no, div, branch, reg_id):
    from app import db, Attendance, app

    try:
        with app.app_context():
            existing_entry = Attendance.query.filter(
                Attendance.name == name,
                Attendance.date == current_date
            ).first()

            current_time_str = datetime.now().strftime("%H:%M:%S")

            if existing_entry:
                existing_entry.end_time = current_time_str
                db.session.commit()
                print("End time updated")
            else:
                new_attendance = Attendance(
                    name=name,
                    start_time=current_time_str,
                    end_time=current_time_str,
                    date=current_date,
                    roll_no=roll_no,
                    division=div,
                    branch=branch,
                    reg_id=reg_id
                )
                db.session.add(new_attendance)
                db.session.commit()
                print("Start and end time recorded (first entry)")
    except Exception as e:
        print("Error:", e)
