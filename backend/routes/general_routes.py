from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, send_from_directory, session, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import and_, asc

from backend.models import Attendance, Student_data, Users, db, SessionCode

import os
import datetime

# Define the general blueprint
general_bp = Blueprint('general_bp', __name__)

# -- Landing Page Route --
@general_bp.route('/landing')
def landing_page():
    return render_template('landing.html', current_year=datetime.datetime.now().year)

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
                filters = [Attendance.session_code_id == session['session_code_id']]

                # Extract known filters
                if 'first_name' in query_parameters:
                    filters.append(Attendance.first_name.ilike(f"%{query_parameters['first_name']}%"))
                if 'last_name' in query_parameters:
                    filters.append(Attendance.last_name.ilike(f"%{query_parameters['last_name']}%"))
                if 'reg_id' in query_parameters:
                    filters.append(Attendance.reg_id.ilike(f"%{query_parameters['reg_id']}%"))
                if 'occupation' in query_parameters:
                    filters.append(Attendance.occupation.ilike(f"%{query_parameters['occupation']}%"))

                if 'regular_wage' in query_parameters:
                    try:
                        wage = float(query_parameters['regular_wage'])
                        filters.append(Attendance.regular_wage == wage)
                    except ValueError:
                        flash("Invalid wage value.", "error")
                        attendance_records = []
                        return render_template('results.html', attendance_records=attendance_records)

                # Handle date range
                start_date_str = query_parameters.get('start_date')
                end_date_str = query_parameters.get('end_date')

                if start_date_str and end_date_str:
                    try:
                        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
                        filters.append(Attendance.date.between(start_date, end_date))
                    except ValueError:
                        flash("Invalid date range format.", "error")
                        attendance_records = []
                        return render_template('results.html', attendance_records=attendance_records)

                attendance_records = Attendance.query.filter(
                    and_(*filters)
                ).order_by(asc(Attendance.reg_id)).all()
            else:
                attendance_records = []
                flash("No parameters provided for query", "warning")
            return render_template(
                'results.html',
                attendance_records=attendance_records,
                start_date=start_date_str,
                end_date=end_date_str
            )
        except Exception as e:
            # Raw exception fallback
            return str(e)
    return 'Unauthorized access'

# -- Admin Image Gallery Route --
@general_bp.route('/images') 
@login_required
def images():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))

    if current_user.role == 'admin':
        from backend.utils.s3_utils import list_files_in_folder, generate_presigned_url

        session_id = str(session['session_code_id'])
        s3_prefix = f"{current_app.config['UPLOAD_FOLDER']}/{session_id}"
        image_keys = list_files_in_folder(s3_prefix)
        image_no = len(image_keys)
        print(f"No of images: {image_no}")

        employees = Student_data.query.filter_by(session_code_id=session_id).all()
        emp_lookup = {emp.regid.upper() + '.JPG': emp for emp in employees}

        images = []
        for filename in image_keys:
            full_key = f"{s3_prefix}/{filename}"
            url = generate_presigned_url(full_key)
            matched_emp = emp_lookup.get(filename.upper())
            images.append({
                'filename': filename,
                'url': url,
                'employee': matched_emp
            })

        return render_template(
            'image_gallery.html',
            images=images,
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
    - Returns a presigned S3 URL that temporarily grants access
    """
    if str(folder) != str(session['session_code_id']):
        return "Unauthorized access", 403
    from backend.utils.s3_utils import generate_presigned_url
    s3_key = f"{current_app.config['UPLOAD_FOLDER']}/{folder}/{filename}"
    url = generate_presigned_url(s3_key)
    if url:
        return redirect(url)
    else:
        return "File not found", 404


# -- Admin Edit Employee Route --
@general_bp.route('/edit_employee', methods=['GET', 'POST'])
@login_required
def edit_employee():
    if current_user.role != 'admin':
        return "Unauthorized access", 403

    regid = request.args.get('regid') if request.method == 'GET' else request.form.get('regid')
    session_id = session.get('session_code_id')

    employee = Student_data.query.filter_by(regid=regid, session_code_id=session_id).first()

    if not employee:
        flash("Employee not found.", "error")
        return redirect(url_for('general_bp.images'))

    if request.method == 'POST':
        employee.first_name = request.form.get('first_name')
        employee.last_name = request.form.get('last_name')
        employee.occupation = request.form.get('occupation')
        employee.regular_wage = float(request.form.get('regular_wage'))
        employee.overtime_wage = float(request.form.get('overtime_wage'))
        employee.regular_hours = int(request.form.get('regular_hours'))
        max_ot = request.form.get('maximum_overtime_hours')
        employee.maximum_overtime_hours = int(max_ot) if max_ot else None

        db.session.commit()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('general_bp.images'))

    return render_template('edit_employee.html', employee=employee)

# -- Admin Delete Employee Route --
@general_bp.route('/delete_employee', methods=['POST'])
@login_required
def delete_employee():
    if current_user.role != 'admin':
        return "Unauthorized access", 403

    regid = request.form.get('regid')
    session_id = session.get('session_code_id')

    if not regid or not session_id:
        flash("Missing data for deletion.", "error")
        return redirect(url_for('general_bp.images'))

    # Step 1: Delete employee record
    employee = Student_data.query.filter_by(regid=regid, session_code_id=session_id).first()
    if employee:
        db.session.delete(employee)
        db.session.commit()
        flash(f"Deleted employee {regid} from database.", "info")
    else:
        flash("Employee not found.", "error")
        return redirect(url_for('general_bp.images'))

    # Step 2: Delete image from S3
    from backend.utils.s3_utils import delete_file
    image_filename = f"{regid.upper()}.jpg"
    s3_key = f"{current_app.config['UPLOAD_FOLDER']}/{session_id}/{image_filename}"
    deleted = delete_file(s3_key)
    if deleted:
        flash("Image deleted from storage.", "success")
    else:
        flash("Failed to delete image file from S3.", "warning")

    return redirect(url_for('general_bp.images'))
