# --- Flask core imports and extensions ---
from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import SQLAlchemyError

# --- Standard library ---
import re
import datetime

# --- Internal modules ---
from backend.models import db, Users, SessionCode, PotentialClient

# --- Initialize Bcrypt ---
bcrypt = Bcrypt()

# --- Define Blueprint for authentication ---
auth_bp = Blueprint('auth_bp', __name__)

# -- Sign Up Route --
@auth_bp.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    error = None
    success = None

    if request.method == 'POST':
        email = request.form.get('email')
        phone_number = request.form.get('phone')

        # Check if already exists
        existing = PotentialClient.query.filter_by(email=email).first()
        if existing:
            error = 'This email has already been submitted. If you need help, contact our team.'
        else:
            try:
                new_client = PotentialClient(email=email, phone_number=phone_number)
                db.session.add(new_client)
                db.session.commit()
                success = 'Your request has been submitted. Our team will reach out soon.'
            except Exception as e:
                db.session.rollback()
                error = 'An error occurred. Please try again later.'
                print(f"[DB ERROR] {e}")

    return render_template('sign_up.html', error=error, success=success, current_year=datetime.datetime.now().year)

# --- Register Blueprint ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration by validating input, checking for existing users,
    hashing the password, and committing a new user to the database.
    """
    error = None
    password_regex = r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if request.method == 'POST':
        # --- Extract form data ---
        username = request.form['username']
        reg_id = request.form['reg_id']
        password = request.form['password']
        role = request.form['role']
        session_code_input = request.form['session_code']
        # --- Lookup session code ---
        session_code_obj = SessionCode.query.filter_by(code=session_code_input).first()
        # --- Hash password securely ---
        hashed_pass = bcrypt.generate_password_hash(password).decode('utf-8')
        # --- Validation checks ---
        existing_user = Users.query.filter_by(username=username).first()
        existing_reg_id = Users.query.filter_by(reg_id=reg_id).first()
        if existing_user:
            error = 'Username already exists!'
            print('[ERROR] Username already exists!')
        elif existing_reg_id:
            error = 'Registration ID already exists!'
            print('[ERROR] Registration ID already exists!')
        elif not re.match(password_regex, password):
            error = (
                'Password must contain at least one uppercase letter, one symbol, '
                'one number, and be at least 8 characters long!'
            )
        elif not session_code_obj:
            error = 'Invalid session code. Please check and try again.'
            print('[ERROR] Invalid session code entered!')
        else:
            # --- Create and add new user ---
            new_user = Users(
                username=username,
                reg_id=reg_id,
                password=hashed_pass,
                role=role,
                session_code_id=session_code_obj.id  # 🔗 Link user to session code
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('auth_bp.login'))
    # --- Render form with error (if any) ---
    return render_template('register.html', error=error)

# --- Login BluePrint ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login by validating credentials and session code,
    then redirecting the user based on their role.
    """
    error_message = None
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        # --- Extract form data ---
        username = request.form.get('username')
        password = request.form.get('password')
        session_code_input = request.form.get('session_code')
        # --- Validate session code ---
        session_code_obj = SessionCode.query.filter_by(code=session_code_input).first()
        if not session_code_obj:
            error_message = 'Invalid session code. Please check and try again.'
            flash(error_message, 'error')
            return redirect(url_for('auth_bp.login', error=error_message))
        try:
            # --- Fetch user by username and session_code_id ---
            user = Users.query.filter_by(username=username, session_code_id=session_code_obj.id).first()
            # --- Validate user credentials ---
            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session['session_code_id'] = user.session_code_id
                success_message = f'Welcome back, {user.username}!'
                flash(success_message, 'success')
                # --- Role-based redirection ---
                if user.role == 'admin':
                    return redirect(url_for('admin_bp.data'))
                elif user.role == 'teacher':
                    return redirect(url_for('general_bp.get_attendance'))
                elif user.role == 'student':
                    return redirect(url_for('general_bp.display_attendance'))
            else:
                error_message = 'Incorrect username or password. Please try again.'
                flash(error_message, 'error')
        except SQLAlchemyError as e:
            error_message = 'An error occurred while processing your request. Please try again later.'
            flash(error_message, 'error')
            print(f'[EXCEPTION] {e}')
    # --- Final fallback ---
    return redirect(url_for('auth_bp.login', error=error_message)) if error_message else redirect(url_for('auth_bp.login'))

# --- Logout Blueprint ---
@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Logs out the current user, clears the session,
    and redirects to the login screen with a success message.
    """
    logout_user()
    session.clear()
    flash('Logout successful!', 'success')
    return redirect(url_for('auth_bp.login'))
