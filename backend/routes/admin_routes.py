from flask import Blueprint, request, redirect, url_for, render_template, flash, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from backend.models import db, Student_data, Attendance, SessionCode
from backend.utils.helpers import allowed_file

import os
import csv
import io
import logging

# Define the admin blueprint
admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/data')
@login_required
def data():
    if current_user.role != 'admin':
        return 'Unauthorized Access'

    session_id = session.get('session_code_id')
    if not session_id:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))

    from backend.utils.s3_utils import get_image_urls_for_session
    from backend.models import Student_data  # already at top

    # Get raw image metadata (filename + presigned URL)
    image_entries = get_image_urls_for_session(session_id)

    # Match each image to an employee by regid (from filename)
    images = []
    for entry in image_entries:
        regid = entry['filename'].rsplit('.', 1)[0].upper()
        employee = Student_data.query.filter_by(regid=regid, session_code_id=session_id).first()
        images.append({
            'filename': entry['filename'],
            'url': entry['url'],
            'employee': employee
        })

    # NEW: If an edit_regid is passed, filter images to only that employee
    edit_regid = request.args.get("edit_regid")
    if edit_regid:
        images = [img for img in images if img['employee'] and img['employee'].regid.upper() == edit_regid.upper()]

    # NEW: If an edit_regid is passed, fetch the corresponding employee
    employee_to_edit = None
    if edit_regid:
        employee_to_edit = Student_data.query.filter_by(
            regid=edit_regid.upper(),
            session_code_id=session_id
        ).first()

    # Fetch all employees for the current session
    employees = Student_data.query.filter_by(session_code_id=session_id).all()

    # Add a .full_name property to each for display
    for emp in employees:
        emp.full_name = f"{emp.last_name}, {emp.first_name}"

    return render_template(
        'admin/data.html',
        active_tab='employee',
        images=images,
        image_no=len(images),
        employee=employee_to_edit,
        employees=employees  # ✅ Now passed to employee_sidebar.html
    )


# -- Weekly Attendance Tab --
@admin_bp.route('/weekly_attendance')
@login_required
def weekly_attendance():
    if current_user.role == 'admin':
        return render_template('admin/data.html', active_tab='weekly')
    return 'Unauthorized Access'

# -- Custom Query Tab --
@admin_bp.route('/query')
@login_required
def custom_query():
    if current_user.role == 'admin':
        return render_template('admin/data.html', active_tab='query')
    return 'Unauthorized Access'

# -- Add User Route --
@admin_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    """
    Handle admin submission of a new student.
    - Validates session and form fields
    - Checks for duplicate student within session
    - Saves uploaded image into session-specific S3 folder
    - Commits new student record to the database
    """
    # Ensure a session code is present
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    # Extract form data
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    occupation = request.form['occupation']
    regular_wage = float(request.form['regular_wage'])
    overtime_wage = float(request.form['overtime_wage'])
    regular_hours = int(request.form['regular_hours'])
    maximum_overtime_hours = request.form.get('maximum_overtime_hours')  # optional
    maximum_overtime_hours = int(maximum_overtime_hours) if maximum_overtime_hours else None
    regid = request.form['reg_id']
    # Check for duplicate
    existing_student = Student_data.query.filter_by(
        regid=regid,
        session_code_id=session['session_code_id']
    ).first()
    if existing_student:
        flash('Student already exists!', 'error')
        return redirect(url_for('admin_bp.data'))
    # Validate image
    if 'image' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    file = request.files['image']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        from backend.utils.s3_utils import upload_file_to_s3
        # Construct secure filename
        extension = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{regid}.{extension}")
        # S3 path: uploads/<session_id>/<filename>
        session_id = session['session_code_id']
        s3_key = upload_file_to_s3(file, folder=f"{current_app.config['UPLOAD_FOLDER']}/{session_id}")

        if s3_key:
            print(f"[DEBUG] Uploaded to S3: {s3_key}")
        else:
            flash("Failed to upload image to cloud storage", "error")
            return redirect(request.url)
        # Create DB record
        user = Student_data(
            first_name=first_name,
            last_name=last_name,
            occupation=occupation,
            regular_wage=regular_wage,
            overtime_wage=overtime_wage,
            regular_hours=regular_hours,
            maximum_overtime_hours=maximum_overtime_hours,
            regid=regid,
            session_code_id=session_id
        )
        db.session.add(user)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('admin_bp.data'))
    flash('Invalid file extension. Allowed extensions are: png, jpg, jpeg, gif', 'error')
    return redirect(request.url)

# -- Download Attendance CSV Route --
@admin_bp.route('/download_attendance_csv', methods=['POST'])
def download_attendance_csv():
    """
    Allow an admin to download filtered attendance records as a CSV for a date range.
    - Requires session_code_id
    - Filters based on optional fields (name, reg_id, branch, division)
    - Requires start_date and end_date
    """
    from flask import Response
    import io
    import csv
    from datetime import datetime
    from sqlalchemy import and_

    if 'session_code_id' not in session:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))

    try:
        # Extract required dates
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        if not start_date_str or not end_date_str:
            flash("Start and end dates must be provided.")
            return redirect(url_for('general_bp.get_attendance'))

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.")
            return redirect(url_for('general_bp.get_attendance'))

        if start_date > end_date:
            flash("Start date must be before or equal to end date.")
            return redirect(url_for('general_bp.get_attendance'))

        if (end_date - start_date).days > 45:
            flash("Date range cannot exceed 45 days.")
            return redirect(url_for('general_bp.get_attendance'))

        # Build filters
        filters = [Attendance.session_code_id == session['session_code_id']]
        filters.append(Attendance.date.between(start_date, end_date))

        # Optional filters from form
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        occupation = request.form.get('occupation')
        regular_wage_str = request.form.get('regular_wage')
        reg_id = request.form.get('reg_id')

        if first_name:
            filters.append(Attendance.first_name.ilike(f"%{first_name}%"))
        if last_name:
            filters.append(Attendance.last_name.ilike(f"%{last_name}%"))
        if reg_id:
            filters.append(Attendance.reg_id.ilike(f"%{reg_id}%"))
        if occupation:
            filters.append(Attendance.occupation.ilike(f"%{occupation}%"))
        if regular_wage_str:
            try:
                regular_wage = float(regular_wage_str)
                filters.append(Attendance.regular_wage == regular_wage)
            except ValueError:
                flash("Invalid wage value.", "error")
                return redirect(url_for('general_bp.get_attendance'))

        # Final query
        attendance_records = Attendance.query.filter(and_(*filters)).all()

        if not attendance_records:
            flash("No attendance records found for the specified filters.")
            return redirect(url_for('general_bp.get_attendance'))

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'First Name', 'Last Name', 'Occupation', 'Regular Wage',
            'Start Time', 'End Time', 'Date', 'Registration ID'
        ])
        for record in attendance_records:
            writer.writerow([
                record.first_name, record.last_name, record.occupation, record.regular_wage,
                record.start_time, record.end_time, record.date, record.reg_id
            ])

        filename = f"attendance_records_{start_date}_to_{end_date}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logging.exception("Error generating CSV file: %s", str(e))
        flash("An error occurred while generating the CSV file.")
        return redirect(url_for('general_bp.get_attendance'))
