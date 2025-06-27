from flask import Flask, render_template, Response, flash, request, redirect, url_for, session, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import asc
from werkzeug.utils import secure_filename
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from sqlalchemy.exc import SQLAlchemyError
import cv2
import pickle
import numpy as np
import face_recognition
import cvzone
import datetime
from datetime import time as datetime_time
import time
import threading
import os
import csv
import io
import logging
import json
import re
from utils.helpers import (
    findEncodings,
    compare,
    get_data,
    mysqlconnect,
    record_attendance,
    bcrypt,
    stop_camera,
)
from models import db, Student_data, Attendance, Users



# Opening all the necessary files needed
with open('config.json') as p:
    params = json.load(p)['params']
encoding_file_path = params['encoding_file_path']
file = open(encoding_file_path, 'rb')
encodeListKnownWithIds = pickle.load(file)
file.close()
encodeListKnown, studentIds = encodeListKnownWithIds

# App configs
app = Flask(__name__)
app.config['SECRET_KEY'] = params['secret_key']
app.config['SQLALCHEMY_DATABASE_URI'] = params['sql_url']
db.init_app(app)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = params['upload_folder']
hostedapp = Flask(__name__)
hostedapp.wsgi_app = DispatcherMiddleware(
    NotFound(), {"/Attendance_system": app})
cert_path = params['cert_path']
key_path = params['key_path']
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

# Register route modules
from routes.auth_routes import auth_bp
from routes.general_routes import general_bp

app.register_blueprint(auth_bp)
app.register_blueprint(general_bp)


# Variables defined
camera = None  # Global variable to store camera object

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))


# Function to start the camera
def start_camera():
    global camera

# Function which does the face recognition and displaying the video feed
def gen_frames(camera, duration=5):
    start_time = time.time()

    while camera is not None and (time.time() - start_time < duration):
        success, frame = camera.read()
        if not success:
            break
        imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
        faceCurFrame = face_recognition.face_locations(imgS)
        encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

        for encodeFace, faceLoc in zip(encodeCurFrame, faceCurFrame):
            matches, facedis, matchIndex = compare(encodeListKnown, encodeFace)
            student_id = get_data(matches, matchIndex, studentIds)
            data = mysqlconnect(student_id)
            name = data[1]
            roll_no = data[2]
            div = data[3]
            branch = data[4]
            reg_id = student_id
            print(name)
            y1, x2, y2, x1 = faceLoc
            y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
            bbox = x1, y1, x2 - x1, y2 - y1
            imgBackground = cvzone.cornerRect(frame, bbox, rt=0)
            cv2.putText(frame, name, (bbox[0], bbox[1] - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 0), 3, lineType=cv2.LINE_AA)
            cv2.putText(imgBackground, reg_id,
                        (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            current_date = datetime.datetime.now().date()
            if student_id:
                t = threading.Thread(target=record_attendance, args=(name, current_date, roll_no, div, branch, reg_id))
                t.start()
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# Route of video feed to flask webpage on index page
@app.route('/video1')
def video1():
    try:
        camera1 = params['camera_index_1']
        camera = cv2.VideoCapture(camera1)
        return Response(gen_frames(camera), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print("Error:", e)
        return "Error connecting to the video stream"


@app.route('/video2')
def video2():
    try:
        camera2 = params['camera_index_2']
        camera = cv2.VideoCapture(camera2)
        return Response(gen_frames(camera), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print("Error:", e)
        return "Error connecting to the video stream"
    

@app.route('/scan/<int:camera_id>')
def start_scan(camera_id):
    try:
        if camera_id == 1:
            cam_index = params['camera_index_1']
        elif camera_id == 2:
            cam_index = params['camera_index_2']
        else:
            return "Invalid camera ID"

        camera = cv2.VideoCapture(cam_index)
        return Response(gen_frames(camera), mimetype='multipart/x-mixed-replace; boundary=frame')

    except Exception as e:
        print("Error in scan route:", e)
        return "Error starting scan"


# Route to add new students page for admins


@app.route('/data')
@login_required
def data():
    if current_user.role == 'admin':
        stop_camera()
        return render_template('data.html')
    else:
        return 'UnAuthorized Access'


@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    name = request.form['name']
    branch = request.form['branch']
    division = request.form['division']
    regid = request.form['reg_id']
    rollno = request.form['roll_no']

    # Check if a student with the same name already exists
    existing_student = Student_data.query.filter_by(name=name).first()

    if existing_student:
        # Student already exists, handle the error (e.g., display a message)
        error_message = 'Student already exists!'
        flash('Student already exists!', 'error')
        return redirect(url_for('data'))
    else:
        # Check if the post request has the file part
        if 'image' not in request.files:
            error_message = 'No file part'
            flash('No file part')
            return redirect(request.url)

        file = request.files['image']

        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            error_message = 'No selected file'
            flash('No selected file')
            return redirect(request.url)

        # Check if the file extension is allowed
        if file and allowed_file(file.filename):
            # Secure the filename to prevent any malicious activity
            filename = secure_filename(
                regid + '.' + file.filename.rsplit('.', 1)[1].lower())
            # Save the file to the upload folder
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Proceed to add the new student
            user = Student_data(name=name, rollno=rollno,
                                division=division, branch=branch, regid=regid)
            db.session.add(user)
            db.session.commit()
            error_message = 'Student added successfully!'
            flash('Student added successfully!', 'success')
            return render_template('data.html', error=error_message)
        else:
            error_message = 'Invalid file extension. Allowed extensions are: png, jpg, jpeg, gif'
            flash(
                'Invalid file extension. Allowed extensions are: png, jpg, jpeg, gif', 'error')
            return redirect(request.url)



# Function to download the attendance of particular date in cvs format


@app.route('/download_attendance_csv', methods=['POST'])
def download_attendance_csv():
    try:
        # Assuming the date is submitted via a form
        date = request.form.get('date')
        if not date:
            flash("Date not provided for downloading.")
            return redirect(url_for('get_attendance'))

        # Retrieve attendance records for the specified date
        attendance_records = Attendance.query.filter_by(date=date).all()

        if not attendance_records:
            flash("No attendance records found for the specified date.")
            return redirect(url_for('get_attendance'))

        # Create a CSV string
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Start Time', 'End Time', 'Date',
                        'Roll Number', 'Division', 'Branch', 'Registration ID'])
        for record in attendance_records:
            writer.writerow([record.name, record.start_time, record.end_time, record.date,
                            record.roll_no, record.division, record.branch, record.reg_id])

        # Save CSV file to a specified folder
        folder_path = 'downloads'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_path = os.path.join(folder_path, f"attendance_records_{date}.csv")
        with open(file_path, 'w') as f:
            # Remove trailing newline characters
            f.write(output.getvalue().strip())

        flash("Attendance records downloaded successfully.")
        error_message = 'Attendance records downloaded successfully.'
        return render_template('results.html', error=error_message)
    except Exception as e:
        logging.exception(
            "Error occurred while generating CSV file: %s", str(e))
        flash("An error occurred while generating CSV file.")
        error_message = 'An error occurred while generating CSV file.'
        return render_template('results.html', error=error_message)

# Route to trigger encoding manually
@app.route('/generate_encodings', methods=['GET', 'POST'])
def generate_encodings():
    if request.method == 'POST':
        # Delete existing encoding file if it exists
        encoding_file_path = "Resources/EncodeFile.p"
        if os.path.exists(encoding_file_path):
            os.remove(encoding_file_path)
            print("File removed")
            flash("File Removed")

        # Importing the student images
        folderPath = 'uploads'
        pathList = os.listdir(folderPath)
        imgList = []
        studentIds = []
        for path in pathList:
            imgList.append(cv2.imread(os.path.join(folderPath, path)))
            studentIds.append(os.path.splitext(path)[0])
            print(os.path.splitext(path)[0])
        # Generate encodings
        try:
            print("Encoding started...")
            error_message = 'Encoding started...'
            flash("Encoding started...", "success")
            encodeListKnown = findEncodings(imgList)
            encodeListKnownWithIds = [encodeListKnown, studentIds]
            print("Encoding complete")
            error_message = 'Encoding complete'
            flash("Encoding complete", "success")
            with open(encoding_file_path, 'wb') as file:
                pickle.dump(encodeListKnownWithIds, file)
            print("File Saved")
            error_message = 'Encodings generated successfully!'
            flash('Encodings generated successfully!', 'success')
        except Exception as e:
            print("Error:", e)
            flash('Error occurred while generating encodings.', 'error')

        # Redirect to homepage or any other page after encoding
        return redirect(url_for('data'))

    return render_template('data.html', error=error_message)


# Route to the index page where the camera feed is displayed
@app.route('/')
def index():
    start_camera()
    return render_template('index.html')


# Function to start to the app
if __name__ == '__main__':
    # app.run(debug=True,ssl_context=("cert.pem", "key.pem"))
    # app.run(debug=True)
    hostedapp.run(debug=True, ssl_context=(
        cert_path, key_path), host='0.0.0.0')
