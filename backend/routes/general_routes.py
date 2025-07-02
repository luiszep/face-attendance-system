from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, send_from_directory, session, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import asc

from models import Attendance, Student_data, Users, db, SessionCode

import os
import datetime

# Define the general blueprint
general_bp = Blueprint('general_bp', __name__)

# -- Student Profile Route --
@general_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """
    Display the student's attendance history for the current session.
    - Accessible only if session_code_id is present and role is 'student'
    - Falls back to session['username'] if reg_id is not on current_user
    """
    # Ensure session is valid
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    if current_user.role == 'student':
        # Attempt to use current_user.reg_id, fallback to session username
        reg_id = session['username']
        if hasattr(current_user, 'reg_id'):
            reg_id = current_user.reg_id
        # Query attendance records for the student in the current session
        data = Attendance.query.filter_by(
            reg_id=reg_id,
            session_code_id=session['session_code_id']
        ).all()
        return render_template(
            'profile.html',
            data=data,
            no_of_attendance=len(data)
        )

# -- Student Daily Attendance Display Route --
@general_bp.route('/display_attendance', methods=['GET', 'POST'])
@login_required
def display_attendance():
    """
    Display attendance for the current student on a selected date.
    - Defaults to today's date if no date is submitted
    - Only available to students
    """
    # Ensure session is valid
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    try:
        # Determine the date to display (default: today)
        current_date = datetime.datetime.now().date()
        input_date = request.form['date'] if request.method == 'POST' else None
        date = input_date or current_date
        data = []
        if current_user.role == 'student':
            # Look up user based on session username
            username = session.get('username')
            user = Users.query.filter_by(username=username).first()
            if user:
                # Query attendance for this student and date
                data = Attendance.query.filter_by(
                    date=date,
                    reg_id=user.reg_id,
                    session_code_id=session['session_code_id']
                ).all()
        return render_template('display_data.html', data=data, date=date)
    except Exception as e:
        # Return raw exception message for now
        return str(e)

# -- Teacher Attendance Query Route --
@general_bp.route('/get_attendance', methods=['GET', 'POST'])
@login_required
def get_attendance():
    """
    Allow a teacher to query attendance records for a specific date or by custom filters.
    - Requires session_code_id and teacher role
    - Accepts a POST form date or GET query parameters
    - Renders results.html with matching attendance records
    """
    # Ensure session is valid
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    if current_user.role == 'teacher':
        try:
            # Get optional date filter from form
            date_filter = request.form.get('date') if request.method == 'POST' else None
            # Build query parameters from GET args
            query_parameters = {
                key: value
                for key, value in request.args.items()
                if value
            }
            query_parameters['session_code_id'] = session['session_code_id']
            # Query by date if provided
            if date_filter:
                attendance_records = Attendance.query.filter_by(
                    date=date_filter,
                    session_code_id=session['session_code_id']
                ).order_by(asc(Attendance.reg_id)).all()
            # Query using filters from query string (e.g., ?reg_id=XYZ)
            elif query_parameters:
                attendance_records = Attendance.query.filter_by(
                    **query_parameters
                ).order_by(asc(Attendance.reg_id)).all()
            # No filters provided
            else:
                attendance_records = []
                flash("No parameters provided for query", "warning")
            return render_template(
                'results.html',
                attendance_records=attendance_records,
                date=date_filter
            )
        except Exception as e:
            # Raw exception fallback
            return str(e)
    return 'Unauthorized access'


# -- Admin Image Gallery Route --
@general_bp.route('/images')
@login_required
def images():
    """
    Allow admin to view all uploaded images for the current session.
    - Lists image filenames in session-specific upload folder
    - Renders image_gallery.html with image count and list
    """
    # Ensure session is valid
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    if current_user.role == 'admin':
        session_folder = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            str(session['session_code_id'])
        )
        image_files = []
        if os.path.exists(session_folder):
            image_files = [
                f for f in os.listdir(session_folder)
                if os.path.isfile(os.path.join(session_folder, f))
            ]
        image_no = len(image_files)
        print(f"No of images: {image_no}")
        return render_template(
            'image_gallery.html',
            image_files=image_files,
            image_no=image_no
        )
    return 'Unauthorized access'

# -- Serve Uploaded Image Securely --
@general_bp.route('/uploads/<folder>/<filename>')
@login_required
def get_image(folder, filename):
    """
    Serve an uploaded image file if the folder matches the current session_code_id.
    - Prevents access to folders outside the active session
    - Sends file from session-specific upload directory
    """
    if str(folder) != str(session['session_code_id']):
        return "Unauthorized access", 403
    folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    return send_from_directory(folder_path, filename)
