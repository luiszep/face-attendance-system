from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, current_user
from sqlalchemy.exc import SQLAlchemyError
import re

from models import db, Users, SessionCode
from utils.helpers import bcrypt


auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None  # Initialize error variable
    password_regex = r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if request.method == 'POST':
        username = request.form['username']
        reg_id = request.form['reg_id']
        password = request.form['password']
        role = request.form['role']
        session_code_input = request.form['session_code']
        session_code_obj = SessionCode.query.filter_by(code=session_code_input).first()
        hashed_pass = bcrypt.generate_password_hash(password).decode('utf-8')
        # Check if username or reg_id already exists
        existing_user = Users.query.filter_by(username=username).first()
        existing_reg_id = Users.query.filter_by(reg_id=reg_id).first()

        if existing_user:
            error = 'Username already exists!'
            print('Username already exists!')
        elif existing_reg_id:
            error = 'Registration ID already exists!'
            print('Registration ID already exists!')
        elif not re.match(password_regex, password):
            error = 'Password must contain at least one uppercase letter, one symbol, one number, and be at least 8 characters long!'
        elif not session_code_obj:
            error = 'Invalid session code. Please check and try again.'
            print('Invalid session code entered!')
        else:
            # Create new user
            new_user = Users(
                username=username,
                reg_id=reg_id,
                password=hashed_pass,
                role=role,
                session_code_id=session_code_obj.id  # 🔗 Link user to session code
            )

            db.session.add(new_user)
            db.session.commit()
            error = 'Registration successfull!'
            flash('Registration successful!', 'success')
            return render_template('login.html', error=error)

    # Pass error variable to template
    return render_template('register.html', error=error)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        session_code_input = request.form.get('session_code')
        session_code_obj = SessionCode.query.filter_by(code=session_code_input).first()
        
        if not session_code_obj:
            error_message = 'Invalid session code. Please check and try again.'
            flash(error_message, 'error')
            return render_template('login.html', error=error_message)
        
        try:
            user = Users.query.filter_by(username=username, session_code_id=session_code_obj.id).first()

            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session['session_code_id'] = user.session_code_id
                error_message = 'Welcome back, {}!'.format(user.username)
                flash(error_message, 'success')
                # Redirect based on the user's role
                if user.role == 'admin':
                    flash(error_message, 'success')
                    return render_template('data.html', error=error_message)
                elif user.role == 'teacher':
                    flash(error_message, 'success')
                    return render_template('results.html', error=error_message)
                elif user.role == 'student':
                    flash(error_message, 'success')
                    return render_template('display_data.html', error=error_message)
            else:
                error_message = 'Incorrect username or password. Please try again.',
                flash('Incorrect username or password. Please try again.', 'error')
        except SQLAlchemyError as e:
            error_message = 'An error occurred while processing your request. Please try again later.'
            flash(
                'An error occurred while processing your request. Please try again later.', 'error')
            # Log the exception for further investigation
            print(e)
    # If the request method is not GET or POST, or if the login process fails for any reason
    return render_template('login.html', error=error_message)


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    error_message = 'Logout Successfully!!'
    logout_user()
    session.clear()
    return render_template('login.html', error=error_message)
