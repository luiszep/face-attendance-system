# --- Standard library ---
import os
import time
import json
import threading
import datetime

# --- Third-party ---
import cv2
import cvzone
import pickle
import face_recognition

from flask import Flask, render_template, Response, flash, request, redirect, url_for, session
from flask_login import LoginManager
from flask_migrate import Migrate
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# --- Local modules ---
from utils.helpers import (
    findEncodings,
    compare,
    get_data,
    mysqlconnect,
    record_attendance,
)
from models import db, Student_data, Attendance, Users, SessionCode


# --- App Directory Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # This file's directory
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))  # Root project directory
TEMPLATE_DIR = os.path.join(ROOT_DIR, 'frontend', 'templates')  # HTML templates
STATIC_DIR = os.path.join(ROOT_DIR, 'frontend', 'static')      # static assets

# --- Load Configuration from JSON File ---
with open('config.json') as config_file:
    params = json.load(config_file)['params']

# --- Flask App Initialization ---
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['params'] = params
app.config['SECRET_KEY'] = params['secret_key']
app.config['SQLALCHEMY_DATABASE_URI'] = params['sql_url']
app.config['UPLOAD_FOLDER'] = params['upload_folder']

# --- Initialize Extensions ---
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

# --- Certificate Paths for HTTPS ---
cert_path = params['cert_path']
key_path = params['key_path']

# --- Dispatcher Middleware (Mounting Flask App under "/Attendance_system") ---
hostedapp = Flask(__name__)  # Container app to serve Flask under a subpath
hostedapp.wsgi_app = DispatcherMiddleware(NotFound(), {
    "/Attendance_system": app
})

# --- Blueprint Registration ---
from routes.auth_routes import auth_bp
from routes.general_routes import general_bp
from routes.admin_routes import admin_bp

# Register app routes
app.register_blueprint(auth_bp)
app.register_blueprint(general_bp)
app.register_blueprint(admin_bp)

# --- Global Camera Instance ---
camera = None  # Will store the active OpenCV camera object (cv2.VideoCapture)

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    """Flask-Login: Load user by ID."""
    return db.session.get(Users, int(user_id))


# --- Camera Control Functions ---
def start_camera():
    """Placeholder for starting a global camera instance."""
    global camera
    # Note: camera assignment handled in scan/video routes directly

def stop_camera():
    """Releases and cleans up the global camera resource."""
    global camera
    if camera is not None:
        camera.release()
        camera = None


def gen_frames(camera, session_code_id, duration=5):
    """
    Generate video frames with real-time face recognition and attendance recording.
    
    Args:
        camera: OpenCV VideoCapture object.
        session_code_id: Numeric ID for the session (used to load encodings).
        duration: Time limit for the stream in seconds (default is 5).
    
    Yields:
        Encoded JPEG frames for HTTP multipart response.
    """

    # --- Validate session and encoding file ---
    if not session_code_id:
        print("Session code missing. Cannot load encodings.")
        return
    
    # Get encoding directory from config
    encoding_dir = app.config['params'].get('encoding_dir', 'Resources')
    encoding_file_path = os.path.join(encoding_dir, f"EncodeFile_{session_code_id}.p")

    if not os.path.exists(encoding_file_path):
        print(f"Encoding file not found: {encoding_file_path}")
        return

    # --- Load known encodings and associated student IDs ---
    with open(encoding_file_path, 'rb') as file:
        encodeListKnownWithIds = pickle.load(file)
    encodeListKnown, studentIds = encodeListKnownWithIds

    # --- Start streaming frames ---
    start_time = time.time()

    while camera is not None and (time.time() - start_time < duration):
        success, frame = camera.read()
        if not success:
            break

        # Resize and convert frame for faster face recognition
        imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

        faceCurFrame = face_recognition.face_locations(imgS)
        encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

        # --- Match and annotate faces ---
        for encodeFace, faceLoc in zip(encodeCurFrame, faceCurFrame):
            matches, facedis, matchIndex = compare(encodeListKnown, encodeFace)
            student_id = get_data(matches, matchIndex, studentIds)
            data = mysqlconnect(student_id, session_code_id)

            name, roll_no, div, branch, reg_id = data[1], data[2], data[3], data[4], student_id
            print(name)

            # Scale face location back to original frame size
            y1, x2, y2, x1 = [v * 4 for v in faceLoc]
            bbox = x1, y1, x2 - x1, y2 - y1

            # Draw bounding box and label
            imgBackground = cvzone.cornerRect(frame, bbox, rt=0)
            cv2.putText(frame, name, (bbox[0], bbox[1] - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 3, lineType=cv2.LINE_AA)
            cv2.putText(imgBackground, reg_id, (bbox[0], bbox[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

            # Record attendance in a separate thread
            if student_id:
                current_date = datetime.datetime.now().date()
                t = threading.Thread(target=record_attendance,
                                     args=(name, current_date, roll_no, div, branch, reg_id, session_code_id))
                t.start()

        # Encode frame as JPEG and yield to browser
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# --- Flask Routes ---
@app.route('/enter-session', methods=['GET', 'POST'])
def enter_session():
    """
    Route to enter a session code manually before accessing the scanner.

    GET: Renders the form for entering a session code.
    POST: Saves the session code to session and redirects to index if valid.
    """
    if request.method == 'POST':
        entered_code = request.form.get('session_code_id')
        if entered_code:
            session['session_code_id'] = entered_code
            flash("Session code accepted!", "success")
            return redirect(url_for('index'))
        else:
            flash("Please enter a valid session code.", "error")
    return render_template('enter_session.html')
    
    

@app.route('/scan/<int:camera_id>')
def start_scan(camera_id):
    session_code_str = session.get('session_code_id')
    if not session_code_str:
        flash("Please enter your session code before scanning.", "error")
        return redirect(url_for('enter_session'))

    # Convert session code string to numeric session ID
    session_obj = SessionCode.query.filter_by(code=session_code_str).first()
    if not session_obj:
        flash("Invalid session code.", "error")
        return redirect(url_for('enter_session'))

    session_id = session_obj.id  # 👈 This will match your file suffix (e.g. 1 → EncodeFile_1.p)

        
    try:
        if camera_id == 1:
            cam_index = params['camera_index_1']
        elif camera_id == 2:
            cam_index = params['camera_index_2']
        else:
            return "Invalid camera ID"

        camera = cv2.VideoCapture(cam_index)

        return Response(gen_frames(camera, session_id), mimetype='multipart/x-mixed-replace; boundary=frame')

    except Exception as e:
        print("Error in scan route:", e)
        return "Error starting scan"


# Route to trigger encoding manually
@app.route('/generate_encodings', methods=['GET', 'POST'])
def generate_encodings():
    if 'session_code_id' not in session:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))

    if request.method == 'POST':
        # Delete existing encoding file if it exists

        encoding_dir = app.config['params'].get('encoding_dir', 'Resources')
        encoding_file_path = os.path.join(encoding_dir, f"EncodeFile_{session['session_code_id']}.p")

        if os.path.exists(encoding_file_path):
            os.remove(encoding_file_path)
            print("File removed")
            flash("File Removed")

        # Importing the student images
        folderPath = os.path.join('uploads', str(session['session_code_id']))
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
        return redirect(url_for('admin_bp.data'))

    return render_template('data.html', error=error_message)


# Route to the index page where the camera feed is displayed
@app.route('/')
def index():
    if 'session_code_id' not in session:
        flash("Please enter a valid session code first.", "error")
        return redirect(url_for('enter_session'))
    start_camera()
    return render_template('index.html')


# --- App Entry Point ---
if __name__ == '__main__':
    # app.run(debug=True,ssl_context=("cert.pem", "key.pem"))
    # app.run(debug=True)
    hostedapp.run(debug=True, ssl_context=(
        cert_path, key_path), host='0.0.0.0')