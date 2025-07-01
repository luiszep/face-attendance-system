from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, session, current_app
from flask_login import login_required, current_user
from sqlalchemy import asc
from models import Attendance, Student_data, Users, db, SessionCode
import datetime, csv, os, logging, io

general_bp = Blueprint('general_bp', __name__)

@general_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))

    if current_user.role == 'student':
        reg_id = session['username']  # default fallback
        if hasattr(current_user, 'reg_id'):
            reg_id = current_user.reg_id

        data = Attendance.query.filter_by(
            reg_id=reg_id,
            session_code_id=session['session_code_id']
        ).all()
        no_of_attendance = len(data)
        return render_template('profile.html', data=data, no_of_attendance=no_of_attendance)
    

# Route which displays the attendance of all student for that current day
@general_bp.route('/display_attendance', methods=['GET', 'POST'])
@login_required
def display_attendance():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))

    current_date = datetime.datetime.now().date()
    try:
        input_date = None
        if request.method == 'POST':
            input_date = request.form['date']
        if input_date is None:
            date = current_date
        else:
            date = input_date

        # STUDENT: see only their own attendance
        if current_user.role == 'student':
            name = session['username']
            username = session.get('username')
            user = Users.query.filter_by(username=username).first()
            if user:
                data = Attendance.query.filter_by(
                    date=date,
                    reg_id=user.reg_id,
                    session_code_id=session['session_code_id']
                ).all()
            else:
                data = []
        else:
            # Fallback (shouldn’t trigger)
            data = []

        return render_template('display_data.html', data=data, date=date)
    except Exception as e:
        return str(e)


@general_bp.route('/get_attendance', methods=['GET', 'POST'])
@login_required
def get_attendance():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))

    if current_user.role == 'teacher':

        try:
            date_filter = request.form.get('date') if request.method == 'POST' else None
            query_parameters = {key: value for key, value in request.args.items() if value}
            query_parameters['session_code_id'] = session['session_code_id']

            if date_filter:
                # Get all attendance records on selected date
                attendance_records = Attendance.query.filter_by(
                    date=date_filter,
                    session_code_id=session['session_code_id']
                ).order_by(asc(Attendance.reg_id)).all()
            elif query_parameters:
                # Use filters if provided
                attendance_records = Attendance.query.filter_by(**query_parameters).order_by(asc(Attendance.reg_id)).all()
            else:
                attendance_records = []
                flash("No parameters provided for query", "warning")

            return render_template('results.html', attendance_records=attendance_records, date=date_filter)

        except Exception as e:
            return str(e)
    else:
        return 'Unauthorized access'


@general_bp.route('/images')
@login_required
def images():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))

    if current_user.role == 'admin':
        session_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(session['session_code_id']))
        image_files = []
        if os.path.exists(session_folder):
            image_files = [f for f in os.listdir(session_folder) if os.path.isfile(os.path.join(session_folder, f))]
        image_no = len(image_files)
        print(f"No of images: {image_no}")
        return render_template('image_gallery.html', image_files=image_files, image_no=image_no)
    else:
        return 'Unauthourized access'


@general_bp.route('/uploads/<folder>/<filename>')
@login_required
def get_image(folder, filename):
    if str(folder) != str(session['session_code_id']):
        return "Unauthorized access", 403
    folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    return send_from_directory(folder_path, filename)
