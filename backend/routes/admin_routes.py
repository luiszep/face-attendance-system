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

# -- Admin Dashboard Route --
@admin_bp.route('/data')
@login_required
def data():
    """
    Render the admin dashboard (data.html) if the user is an admin.
    """
    if current_user.role == 'admin':
        return render_template('data.html')
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
        return render_template('data.html', error='Student added successfully!')
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
        name = request.form.get('name')
        reg_id = request.form.get('reg_id')
        branch = request.form.get('branch')
        division = request.form.get('division')

        if name:
            filters.append(Attendance.name.ilike(f"%{name}%"))
        if reg_id:
            filters.append(Attendance.reg_id.ilike(f"%{reg_id}%"))
        if branch:
            filters.append(Attendance.branch.ilike(f"%{branch}%"))
        if division:
            filters.append(Attendance.division.ilike(f"%{division}%"))

        # Final query
        attendance_records = Attendance.query.filter(and_(*filters)).all()

        if not attendance_records:
            flash("No attendance records found for the specified filters.")
            return redirect(url_for('general_bp.get_attendance'))

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Name', 'Start Time', 'End Time', 'Date',
            'Roll Number', 'Division', 'Branch', 'Registration ID'
        ])
        for record in attendance_records:
            writer.writerow([
                record.name, record.start_time, record.end_time, record.date,
                record.roll_no, record.division, record.branch, record.reg_id
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
