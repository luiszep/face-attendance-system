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
from dotenv import load_dotenv  

# --- Local modules ---
from backend.utils.helpers import (
    findEncodings,
    compare,
    get_data,
    mysqlconnect,
    record_attendance,
)
from backend.models import db, Student_data, Attendance, Users, SessionCode
from backend.utils.s3_utils import load_encoding_from_s3, save_encoding_to_s3


# --- App Directory Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # This file's directory
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))  # Root project directory
TEMPLATE_DIR = os.path.join(ROOT_DIR, 'frontend', 'templates')  # HTML templates
STATIC_DIR = os.path.join(ROOT_DIR, 'frontend', 'static')      # static assets

# --- Load Environment Variables ---
load_dotenv()  # loads from .env file

# --- Flask App Initialization ---
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['ENCODING_DIR'] = os.environ.get('ENCODING_DIR', 'Resources')
app.config['CAMERA_INDEX_1'] = int(os.environ.get('CAMERA_INDEX_1', 0))
app.config['CAMERA_INDEX_2'] = int(os.environ.get('CAMERA_INDEX_2', 1))
app.config['USE_SSL'] = os.environ.get('USE_SSL', 'false').lower() == 'true'
app.config['CERT_PATH'] = os.environ.get('CERT_PATH', 'keys/cert.pem')
app.config['KEY_PATH'] = os.environ.get('KEY_PATH', 'keys/key.pem')

# --- Initialize Extensions ---
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

# --- Certificate Paths for HTTPS ---
cert_path = app.config['CERT_PATH']
key_path = app.config['KEY_PATH']

# --- Dispatcher Middleware (Mounting Flask App under "/Attendance_system") ---
hostedapp = Flask(__name__)  # Container app to serve Flask under a subpath
hostedapp.wsgi_app = DispatcherMiddleware(NotFound(), {
    "/Attendance_system": app
})

# --- Blueprint Registration ---
from backend.routes.auth_routes import auth_bp
from backend.routes.general_routes import general_bp
from backend.routes.admin_routes import admin_bp

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

# --- Function to Generate Video Frames ---
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
    # --- Load known encodings and associated student IDs from S3 ---
    encodeListKnownWithIds = load_encoding_from_s3(session_code_id)
    if not encodeListKnownWithIds:
        print(f"[S3] Encoding file not found for session: {session_code_id}")
        return
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
            first_name, last_name, occupation, regular_wage = data[1], data[2], data[3], data[4]
            reg_id = student_id
            print(f"{first_name} {last_name}")
            # Scale face location back to original frame size
            y1, x2, y2, x1 = [v * 4 for v in faceLoc]
            bbox = x1, y1, x2 - x1, y2 - y1
            # Draw bounding box and label
            imgBackground = cvzone.cornerRect(frame, bbox, rt=0)
            cv2.putText(frame, first_name, (bbox[0], bbox[1] - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 3, lineType=cv2.LINE_AA)
            cv2.putText(imgBackground, reg_id, (bbox[0], bbox[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            # Record attendance in a separate thread
            if student_id:
                current_date = datetime.datetime.now().date()
                t = threading.Thread(target=record_attendance,
                                    args=(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id))
                t.start()
        # Encode frame as JPEG and yield to browser
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# --- Route to enter session code manually ---
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

# --- Route to start live face recognition scan ---
@app.route('/scan/<int:camera_id>')
def start_scan(camera_id):
    """
    Route to start live face recognition using the specified camera.
    Args:
        camera_id (int): ID to select which camera index to use (e.g. 1 or 2).
    Returns:
        Flask Response streaming video frames with real-time face recognition.
    """
    # --- Validate session code from user ---
    session_code_str = session.get('session_code_id')
    if not session_code_str:
        flash("Please enter your session code before scanning.", "error")
        return redirect(url_for('enter_session'))
    # --- Look up session record by code ---
    session_obj = SessionCode.query.filter_by(code=session_code_str).first()
    if not session_obj:
        flash("Invalid session code.", "error")
        return redirect(url_for('enter_session'))
    session_id = session_obj.id  # Used to identify encoding file (EncodeFile_<id>.p)
    # --- Determine camera index from config ---
    try:
        if camera_id == 1:
            cam_index = app.config['CAMERA_INDEX_1']
        elif camera_id == 2:
            cam_index = app.config['CAMERA_INDEX_2']
        else:
            return "Invalid camera ID"
        # Open camera stream
        camera = cv2.VideoCapture(cam_index)
        # Stream video frames from gen_frames()
        return Response(
            gen_frames(camera, session_id),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        print(f"[ERROR] Scan route failed: {e}")
        return "Error starting scan"

# --- Route to trigger face encoding generation manually ---
@app.route('/generate_encodings', methods=['GET', 'POST'])
def generate_encodings():
    """
    Admin-only route to generate facial encodings for uploaded student images.
    GET  -> Renders the admin data upload page.
    POST -> Deletes existing encoding file (if any), processes student images,
            generates encodings, saves to .p file, and flashes status updates.
    """
    if 'session_code_id' not in session:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))
    if request.method == 'POST':
        session_id = session['session_code_id']

        # --- Load student images from upload folder ---
        from backend.utils.s3_utils import list_files_in_folder
        s3_prefix = f"{app.config['UPLOAD_FOLDER']}/{session_id}"
        path_list = list_files_in_folder(s3_prefix)
        img_list, student_ids = [], []
        for path in path_list:
            from backend.utils.s3_utils import load_image_from_s3
            s3_key = f"{app.config['UPLOAD_FOLDER']}/{session_id}/{path}"
            img = load_image_from_s3(s3_key)
            if img is not None:
                img_list.append(img)
                student_ids.append(os.path.splitext(path)[0])
                print(f"[INFO] Found image for student ID: {student_ids[-1]}")
            else:
                print(f"[WARNING] Could not load image: {s3_key}")
        # --- Generate and save encodings ---
        try:
            print("[INFO] Encoding started...")
            flash("Encoding started...", "success")
            encode_list_known = findEncodings(img_list)
            encode_list_with_ids = [encode_list_known, student_ids]
            success = save_encoding_to_s3(session_id, encode_list_with_ids)
            if success:
                print("[S3] Encoding complete. File saved to S3.")
                flash("Encodings generated successfully!", "success")
            else:
                print("[S3 ERROR] Failed to save encoding to S3.")
                flash("Failed to save encoding to cloud.", "error")
        except Exception as e:
            print(f"[ERROR] Encoding failed: {e}")
            flash("Error occurred while generating encodings.", "error")
        return redirect(url_for('admin_bp.data'))
    # --- Render page for GET request ---
    return render_template('admin/data.html')

# --- Index Route ---
@app.route('/')
def index():
    """
    Home route where the camera feed interface is displayed.
    Redirects users to session entry if no valid session code is found.
    """
    if 'session_code_id' not in session:
        flash("Please enter a valid session code first.", "error")
        return redirect(url_for('enter_session'))
    return render_template('index.html')

if __name__ == '__main__':
    """
    Entry point for launching the app in development mode.
    Uses HTTPS with mkcert-generated certificates. Hosts the mounted app on all network interfaces.
    """
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'

    # Use SSL if enabled
    if app.config['USE_SSL']:
        cert_path = app.config['CERT_PATH']
        key_path = app.config['KEY_PATH']
        ssl_context = (cert_path, key_path)
    else:
        ssl_context = None

    hostedapp.run(
        debug=debug_mode,
        host='0.0.0.0',
        ssl_context=ssl_context
    )


