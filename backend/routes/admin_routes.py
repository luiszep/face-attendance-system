from flask import Blueprint, request, redirect, url_for, render_template, flash, session, current_app
from flask_login import login_required, current_user
from models import db, Student_data, Attendance, SessionCode
from werkzeug.utils import secure_filename
import os
import csv
import io
import logging
from utils.helpers import stop_camera, allowed_file

admin_bp = Blueprint('admin_bp', __name__)


@admin_bp.route('/data')
@login_required
def data():
    if current_user.role == 'admin':
        return render_template('data.html')
    else:
        return 'UnAuthorized Access'
    

@admin_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if 'session_code_id' not in session:
        flash('Session expired or unauthorized access.', 'error')
        return redirect(url_for('auth_bp.login'))
    
    name = request.form['name']
    branch = request.form['branch']
    division = request.form['division']
    regid = request.form['reg_id']
    rollno = request.form['roll_no']

    # Check if a student with the same name already exists
    existing_student = Student_data.query.filter_by(
        name=name,
        session_code_id=session['session_code_id']
    ).first()

    if existing_student:
        # Student already exists, handle the error (e.g., display a message)
        error_message = 'Student already exists!'
        flash('Student already exists!', 'error')
        return redirect(url_for('admin_bp.data'))
    else:
        # Check if the post request has the file part
        if 'image' not in request.files:
            error_message = 'No file part'
            flash('No file part')
            return redirect(request.url)

        file = request.files['image']

        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            error_message = 'No selected file'
            flash('No selected file')
            return redirect(request.url)

        # Check if the file extension is allowed
        if file and allowed_file(file.filename):
            # Create a subfolder for this session_code_id if it doesn't exist
            session_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(session['session_code_id']))
            os.makedirs(session_folder, exist_ok=True)

            # Save the file into the session-specific subfolder
            filename = secure_filename(regid + '.' + file.filename.rsplit('.', 1)[1].lower())
            file_path = os.path.join(session_folder, filename)
            file.save(file_path)

            # Proceed to add the new student
            user = Student_data(
                name=name,
                rollno=rollno,
                division=division,
                branch=branch,
                regid=regid,
                session_code_id=session['session_code_id']  # 🔐 Add this line
            )
            db.session.add(user)
            db.session.commit()
            error_message = 'Student added successfully!'
            flash('Student added successfully!', 'success')
            return render_template('data.html', error=error_message)
        else:
            error_message = 'Invalid file extension. Allowed extensions are: png, jpg, jpeg, gif'
            flash(
                'Invalid file extension. Allowed extensions are: png, jpg, jpeg, gif', 'error')
            return redirect(request.url)


# Function to download the attendance of particular date in cvs format
@admin_bp.route('/download_attendance_csv', methods=['POST'])
def download_attendance_csv():
    if 'session_code_id' not in session:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))

    try:
        # Assuming the date is submitted via a form
        date = request.form.get('date')
        if not date:
            flash("Date not provided for downloading.")
            return redirect(url_for('general_bp.get_attendance'))

        # Retrieve attendance records for the specified date
        attendance_records = Attendance.query.filter_by(
            date=date,
            session_code_id=session['session_code_id']
        ).all()
        if not attendance_records:
            flash("No attendance records found for the specified date.")
            return redirect(url_for('general_bp.get_attendance'))

        # Create a CSV string
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Start Time', 'End Time', 'Date',
                        'Roll Number', 'Division', 'Branch', 'Registration ID'])
        for record in attendance_records:
            writer.writerow([record.name, record.start_time, record.end_time, record.date,
                            record.roll_no, record.division, record.branch, record.reg_id])
        
        # Set the response headers for CSV download
        from flask import Response

        session_id = session['session_code_id']
        filename = f"attendance_records_{session_id}_{date}.csv"

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logging.exception(
            "Error occurred while generating CSV file: %s", str(e))
        flash("An error occurred while generating CSV file.")
        error_message = 'An error occurred while generating CSV file.'
        return render_template('results.html', error=error_message)
