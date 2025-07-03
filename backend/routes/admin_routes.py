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
    - Saves uploaded image into session-specific folder
    - Commits new student record to the database
    """
    # Ensure a session code is present
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    # Extract form data
    name = request.form['name']
    branch = request.form['branch']
    division = request.form['division']
    regid = request.form['reg_id']
    rollno = request.form['roll_no']
    # Check if a student with the same name already exists for this session
    existing_student = Student_data.query.filter_by(
        name=name,
        session_code_id=session['session_code_id']
    ).first()
    if existing_student:
        flash('Student already exists!', 'error')
        return redirect(url_for('admin_bp.data'))
    # Ensure an image was submitted
    if 'image' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    file = request.files['image']
    # Ensure a file was selected
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(request.url)
    # Validate and save the image file
    if file and allowed_file(file.filename):
        # Build session-specific upload folder
        session_folder = os.path.abspath(
            os.path.join(
                current_app.root_path, '..',
                current_app.config['UPLOAD_FOLDER'],
                str(session['session_code_id'])
            )
        )
        os.makedirs(session_folder, exist_ok=True)
        # Construct secure filename using reg ID
        extension = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{regid}.{extension}")
        file_path = os.path.join(session_folder, filename)
        print(f"[DEBUG] Upload folder: {session_folder}")
        print(f"[DEBUG] Saving image as: {file_path}")
        file.save(file_path)
        # Create and commit new student record
        user = Student_data(
            name=name,
            rollno=rollno,
            division=division,
            branch=branch,
            regid=regid,
            session_code_id=session['session_code_id']
        )
        db.session.add(user)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return render_template('data.html', error='Student added successfully!')
    # If file extension is invalid
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
