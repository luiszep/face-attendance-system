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
from flask_login import LoginManager, login_required, current_user
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
login_manager.login_view = 'auth_bp.login'  # Redirect unauthorized users to login page
login_manager.login_message = 'Please log in with admin credentials to access this page.'
login_manager.login_message_category = 'info'

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
def gen_frames(camera, session_code_id, duration=10):
    """
    Generate video frames with real-time face recognition and attendance recording.
    Args:
        camera: OpenCV VideoCapture object.
        session_code_id: Numeric ID for the session (used to load encodings).
        duration: Time limit for the stream in seconds (default is 10).
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
    recognized_any_employee = False
    
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
            
            # Draw bounding box and simple labels
            imgBackground = cvzone.cornerRect(frame, bbox, rt=0)
            
            # Employee name (yellow, prominent)
            cv2.putText(frame, f"{first_name} {last_name}", (bbox[0], bbox[1] - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 3, lineType=cv2.LINE_AA)
            
            # Employee ID (cyan, below name)
            cv2.putText(frame, reg_id, (bbox[0], bbox[1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, lineType=cv2.LINE_AA)
            # Record attendance in a separate thread
            if student_id:
                recognized_any_employee = True
                current_date = datetime.datetime.now().date()
                t = threading.Thread(target=record_attendance,
                                    args=(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id))
                t.start()
        # Encode frame as JPEG and yield to browser
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    
    # After scan duration ends, store result if no employee was recognized
    if not recognized_any_employee:
        from backend.utils.helpers import last_scan_results
        
        # Store "not recognized" result
        last_scan_results['no_recognition'] = {
            'result': 'not_recognized',
            'message': 'Not recognized. Please try again.',
            'timestamp': datetime.datetime.now(),
            'employee_recognized': False
        }


# --- Route to enter session code manually ---
@app.route('/enter-session', methods=['GET', 'POST'])
def enter_session():
    """
    Route to handle session code entry and scanning.
    Supports persistent local session code storage for business deployment.
    """
    from backend.utils.session_manager import session_manager
    
    if request.method == 'POST':
        entered_code = request.form.get('session_code_id')
        scan_action = request.form.get('scan_action')  # 'checkin' or 'checkout'
        business_name = request.form.get('business_name', '').strip()
        save_locally = request.form.get('save_locally') == 'true'
        
        # Handle session code entry (first-time setup or update)
        if entered_code and not scan_action:
            # Save session code locally if requested
            if save_locally:
                success = session_manager.set_session_code(entered_code, business_name)
                if success:
                    flash("Session code saved locally! You won't need to enter it again.", "success")
                else:
                    flash("Failed to save session code locally.", "error")
            
            # Set session code for current session
            session['session_code_id'] = entered_code
            
            # Show the action buttons
            business_info = session_manager.get_business_info()
            return render_template('enter_session.html', 
                                 show_actions=True,
                                 session_code=entered_code,
                                 business_info=business_info)
        
        # Handle scan action (check-in/check-out)
        elif scan_action:
            # Use current session code or saved code
            current_code = session.get('session_code_id') or session_manager.get_session_code()
            
            if not current_code:
                flash("Session code required.", "error")
                return render_template('enter_session.html')
            
            session['session_code_id'] = current_code
            session['intended_action'] = scan_action
            
            # Clear any previous scan results
            from backend.utils.helpers import last_scan_results
            last_scan_results.clear()
            
            # Start scanning immediately with appropriate theme
            if scan_action == 'checkin':
                return render_template('checkin_scan.html', start_scan_immediately=True)
            else:
                return render_template('checkout_scan.html', start_scan_immediately=True)
        
        else:
            flash("Please enter a valid session code.", "error")
    
    # GET request - check if session code is already configured
    business_info = session_manager.get_business_info()
    
    if business_info['is_configured']:
        # Auto-load saved session code
        session['session_code_id'] = business_info['session_code']
        return render_template('enter_session.html', 
                             show_actions=True,
                             session_code=business_info['session_code'],
                             business_info=business_info)
    
    # No saved session code - show entry form
    return render_template('enter_session.html', business_info=business_info)

# --- Route to update session settings ---
@app.route('/session-settings', methods=['GET', 'POST'])
def session_settings():
    """
    Route to update session code settings for businesses.
    Uses standalone authentication for local deployment.
    """
    from backend.utils.session_manager import session_manager
    
    # Check if user is authenticated locally
    if 'admin_authenticated' not in session or not session.get('admin_authenticated'):
        return redirect(url_for('admin_login'))
    
    # Check authentication timeout (30 minutes)
    import time
    auth_time = session.get('admin_auth_time', 0)
    if time.time() - auth_time > 1800:  # 30 minutes
        session.pop('admin_authenticated', None)
        flash("Session expired. Please log in again.", "info")
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            new_code = request.form.get('new_session_code')
            business_name = request.form.get('business_name', '').strip()
            
            if new_code:
                success = session_manager.set_session_code(new_code, business_name)
                if success:
                    session['session_code_id'] = new_code
                    flash("Session code updated successfully!", "success")
                    return redirect(url_for('enter_session'))
                else:
                    flash("Failed to update session code.", "error")
            else:
                flash("Please enter a valid session code.", "error")
        
        elif action == 'clear':
            success = session_manager.clear_session_code()
            if success:
                session.pop('session_code_id', None)
                flash("Session code cleared. You can now enter a new one.", "success")
                return redirect(url_for('enter_session'))
            else:
                flash("Failed to clear session code.", "error")
    
    business_info = session_manager.get_business_info()
    return render_template('session_settings.html', business_info=business_info)

# --- Standalone Admin Login for Local Deployment ---
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """
    Standalone admin login for local session settings.
    Uses environment variables for credentials.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Get admin credentials from local config
        from backend.utils.session_manager import session_manager
        admin_creds = session_manager.get_admin_credentials()
        admin_username = admin_creds['username']
        admin_password = admin_creds['password']
        
        if username == admin_username and password == admin_password:
            import time
            session['admin_authenticated'] = True
            session['admin_auth_time'] = time.time()
            
            # Redirect to originally requested page
            next_page = request.args.get('next', url_for('session_settings'))
            return redirect(next_page)
        else:
            flash("Invalid credentials. Please try again.", "error")
    
    return render_template('admin_login.html')

# --- Admin Logout for Local Deployment ---
@app.route('/admin-logout')
def admin_logout():
    """Clear local admin authentication."""
    session.pop('admin_authenticated', None)
    session.pop('admin_auth_time', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('enter_session'))

# --- Check-in Scan Route ---
@app.route('/checkin-scan')
def checkin_scan():
    """Display the check-in scan interface."""
    # Verify session code exists
    from backend.utils.session_manager import session_manager
    current_code = session.get('session_code_id') or session_manager.get_session_code()
    
    if not current_code:
        flash("Please enter your session code first.", "error")
        return redirect(url_for('enter_session'))
    
    # Ensure session code is set
    session['session_code_id'] = current_code
    session['intended_action'] = 'checkin'
    
    # Clear any previous scan results
    from backend.utils.helpers import last_scan_results
    last_scan_results.clear()
    
    return render_template('checkin_scan.html')

# --- Check-out Scan Route ---
@app.route('/checkout-scan')
def checkout_scan():
    """Display the check-out scan interface."""
    # Verify session code exists
    from backend.utils.session_manager import session_manager
    current_code = session.get('session_code_id') or session_manager.get_session_code()
    
    if not current_code:
        flash("Please enter your session code first.", "error")
        return redirect(url_for('enter_session'))
    
    # Ensure session code is set
    session['session_code_id'] = current_code
    session['intended_action'] = 'checkout'
    
    # Clear any previous scan results
    from backend.utils.helpers import last_scan_results
    last_scan_results.clear()
    
    return render_template('checkout_scan.html')

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
    Home route redirects to the main session entry interface.
    """
    return redirect(url_for('enter_session'))

# --- API Route to Get Scan Result ---
@app.route('/api/scan_result/<reg_id>')
def get_scan_result_api(reg_id):
    """
    API endpoint to get the result of the last scan for simple UI display.
    
    Args:
        reg_id (str): Employee registration ID
        
    Returns:
        JSON response with scan result message
    """
    from flask import jsonify
    from backend.utils.helpers import last_scan_results
    
    # Validate session
    if 'session_code_id' not in session:
        return jsonify({'error': 'Session not found'}), 401
    
    try:
        # Get the last scan result for this employee
        if reg_id in last_scan_results:
            result = last_scan_results[reg_id]
            return jsonify({
                'success': True,
                'message': result['message'],
                'result': result['result'],
                'employee_recognized': result['employee_recognized'],
                'timestamp': result['timestamp'].isoformat() if result['timestamp'] else None
            })
        elif 'no_recognition' in last_scan_results:
            # No face was recognized during the scan
            result = last_scan_results['no_recognition']
            return jsonify({
                'success': False,
                'message': result['message'],
                'result': result['result'],
                'employee_recognized': result['employee_recognized'],
                'timestamp': result['timestamp'].isoformat() if result['timestamp'] else None
            })
        else:
            # No result found - this shouldn't happen in normal operation
            return jsonify({
                'success': False,
                'message': 'No scan result available. Please try again.',
                'result': 'no_result',
                'employee_recognized': False
            })
            
    except Exception as e:
        print(f"[ERROR] Scan result API failed: {e}")
        return jsonify({
            'success': False,
            'message': 'Error processing scan. Please try again.',
            'result': 'error',
            'employee_recognized': False
        }), 500

# --- API Route to Clear Scan Results (for testing) ---
@app.route('/api/clear_scan_results')
def clear_scan_results():
    """Clear all scan results for testing purposes."""
    from flask import jsonify
    from backend.utils.helpers import last_scan_results
    
    last_scan_results.clear()
    return jsonify({'success': True, 'message': 'Scan results cleared'})

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


