from flask import Blueprint, request, redirect, url_for, render_template, flash, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from backend.models import db, Student_data, Attendance, SessionCode
from backend.utils.helpers import allowed_file

import os
import csv
import io
import logging
import datetime

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

    # Get business name from session code
    session_code_obj = SessionCode.query.get(session_id)
    business_name = session_code_obj.business_name if session_code_obj else "Unknown Business"

    from backend.utils.s3_utils import get_image_urls_for_session
    from backend.models import Student_data  # already at top

    # Get raw image metadata (filename + presigned URL)
    image_entries = get_image_urls_for_session(session_id)

    # Match each image to an employee by regid (from filename)
    images = []
    for entry in image_entries:
        regid = entry['filename'].rsplit('.', 1)[0].upper()
        employee = Student_data.query.filter(Student_data.regid.ilike(regid), Student_data.session_code_id == session_id).first()
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
        employee_to_edit = Student_data.query.filter(
            Student_data.regid.ilike(edit_regid),
            Student_data.session_code_id == session_id
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
        employees=employees,  # ✅ Now passed to employee_sidebar.html
        business_name=business_name  # ✅ Pass business name to template
    )


# -- Weekly Attendance Tab --
@admin_bp.route('/weekly_attendance')
@login_required
def weekly_attendance():
    if current_user.role == 'admin':
        session_id = session.get('session_code_id')
        session_code_obj = SessionCode.query.get(session_id) if session_id else None
        business_name = session_code_obj.business_name if session_code_obj else "Unknown Business"
        return render_template('admin/data.html', active_tab='weekly', business_name=business_name)
    return 'Unauthorized Access'

# -- Attendance Results Tab --
@admin_bp.route('/attendance')
@login_required
def attendance():
    if current_user.role != 'admin':
        return 'Unauthorized Access'
    
    session_id = session.get('session_code_id')
    if not session_id:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))
    
    session_code_obj = SessionCode.query.get(session_id)
    business_name = session_code_obj.business_name if session_code_obj else "Unknown Business"
    
    # Get filter parameters
    current_view = request.args.get('view', 'daily')
    selected_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    name_filter = request.args.get('name', '')
    id_filter = request.args.get('id', '')
    occupation_filter = request.args.get('occupation', '')
    
    # Get Quick Filter parameters
    show_present = request.args.get('show_present', 'true') == 'true'
    show_absent = request.args.get('show_absent', 'false') == 'true'
    show_incomplete = request.args.get('show_incomplete', 'false') == 'true'
    
    # Initialize attendance_data as empty
    attendance_data = []
    absent_employees = []
    
    # Only fetch data for daily view for now
    if current_view == 'daily':
        from sqlalchemy import and_
        from backend.models import TimeEntry, Student_data
        
        try:
            # Parse the selected date
            date_obj = datetime.datetime.strptime(selected_date, '%Y-%m-%d').date()
            
            # Build filters for Attendance table
            attendance_filters = [
                Attendance.session_code_id == session_id,
                Attendance.date == date_obj
            ]
            
            # Add search filters
            if name_filter:
                attendance_filters.append(
                    db.or_(
                        Attendance.first_name.ilike(f"%{name_filter}%"),
                        Attendance.last_name.ilike(f"%{name_filter}%")
                    )
                )
            if id_filter:
                attendance_filters.append(Attendance.reg_id.ilike(f"%{id_filter}%"))
            if occupation_filter:
                attendance_filters.append(Attendance.occupation.ilike(f"%{occupation_filter}%"))
            
            # Query Attendance table for daily summaries, ordered by first seen (start_time)
            attendance_records = Attendance.query.filter(and_(*attendance_filters)).order_by(Attendance.start_time.asc()).all()
            
            # For each attendance record, get corresponding TimeEntry records
            for attendance_record in attendance_records:
                # Get TimeEntry records for this employee on this date
                time_entries = TimeEntry.query.filter(
                    and_(
                        TimeEntry.reg_id.ilike(attendance_record.reg_id),
                        TimeEntry.session_code_id == session_id,
                        TimeEntry.date == date_obj
                    )
                ).order_by(TimeEntry.timestamp.asc()).all()
                
                # Calculate total hours from time entries
                total_hours = 0
                current_checkin = None
                
                for entry in time_entries:
                    if entry.entry_type == 'check_in':
                        current_checkin = entry.timestamp
                    elif entry.entry_type == 'check_out' and current_checkin:
                        # Calculate hours for this session
                        time_diff = entry.timestamp - current_checkin
                        session_hours = time_diff.total_seconds() / 3600
                        total_hours += session_hours
                        current_checkin = None
                
                # Prepare data structure
                employee_data = {
                    'reg_id': attendance_record.reg_id,
                    'first_name': attendance_record.first_name,
                    'last_name': attendance_record.last_name,
                    'occupation': attendance_record.occupation,
                    'start_time': attendance_record.start_time,
                    'end_time': attendance_record.end_time,
                    'date': attendance_record.date.strftime('%Y-%m-%d'),
                    'total_hours': round(total_hours, 2),
                    'time_entries': []
                }
                
                # Add time entries with proper formatting
                for entry in time_entries:
                    employee_data['time_entries'].append({
                        'entry_type': entry.entry_type,
                        'sequence_number': entry.sequence_number,
                        'timestamp': entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                attendance_data.append(employee_data)
            
            # Find absent employees (those with no attendance record for this date)
            present_reg_ids = {emp['reg_id'] for emp in attendance_data}
            all_employees = Student_data.query.filter_by(session_code_id=session_id).all()
            
            for employee in all_employees:
                if not any(emp_id.upper() == employee.regid.upper() for emp_id in present_reg_ids):
                    # Apply name filters to absent employees too
                    if name_filter and not (name_filter.lower() in employee.first_name.lower() or name_filter.lower() in employee.last_name.lower()):
                        continue
                    if id_filter and id_filter.lower() not in employee.regid.lower():
                        continue
                    if occupation_filter and occupation_filter.lower() not in employee.occupation.lower():
                        continue
                    
                    absent_employee = {
                        'reg_id': employee.regid,
                        'first_name': employee.first_name,
                        'last_name': employee.last_name,
                        'occupation': employee.occupation,
                        'start_time': None,
                        'end_time': None,
                        'date': selected_date,
                        'total_hours': 0,
                        'time_entries': [],
                        'is_absent': True
                    }
                    absent_employees.append(absent_employee)
                
        except ValueError:
            flash("Invalid date format.", "error")
        except Exception as e:
            flash(f"Error fetching attendance data: {str(e)}", "error")
    
    return render_template(
        'admin/data.html', 
        active_tab='attendance', 
        business_name=business_name,
        attendance_data=attendance_data,
        absent_employees=absent_employees,
        selected_date=selected_date,
        current_view=current_view,
        show_present=show_present,
        show_absent=show_absent,
        show_incomplete=show_incomplete
    )

# -- Custom Query Tab --
@admin_bp.route('/query')
@login_required
def custom_query():
    if current_user.role == 'admin':
        session_id = session.get('session_code_id')
        session_code_obj = SessionCode.query.get(session_id) if session_id else None
        business_name = session_code_obj.business_name if session_code_obj else "Unknown Business"
        return render_template('admin/data.html', active_tab='query', business_name=business_name)
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
    existing_student = Student_data.query.filter(
        Student_data.regid.ilike(regid),
        Student_data.session_code_id == session['session_code_id']
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

# -- Download Daily Attendance CSV Route --
@admin_bp.route('/download_daily_attendance_csv', methods=['POST'])
def download_daily_attendance_csv():
    """
    Download the daily attendance records as CSV based on current filters.
    """
    from flask import Response
    import io
    import csv
    from datetime import datetime
    from sqlalchemy import and_
    from backend.models import TimeEntry, Student_data

    if 'session_code_id' not in session:
        flash("Session expired or unauthorized access.", "error")
        return redirect(url_for('auth_bp.login'))

    try:
        session_id = session['session_code_id']
        
        # Get filter parameters
        selected_date = request.form.get('selected_date', datetime.today().strftime('%Y-%m-%d'))
        show_present = request.form.get('show_present', 'true') == 'true'
        show_absent = request.form.get('show_absent', 'false') == 'true'
        show_incomplete = request.form.get('show_incomplete', 'false') == 'true'
        
        # Parse the selected date
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # Get attendance records for the selected date
        attendance_records = Attendance.query.filter(
            and_(
                Attendance.session_code_id == session_id,
                Attendance.date == date_obj
            )
        ).all()
        
        # Process attendance data
        attendance_data = []
        for attendance_record in attendance_records:
            # Get all time entries for this employee on this date
            time_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.reg_id == attendance_record.reg_id,
                    TimeEntry.date == date_obj,
                    TimeEntry.session_code_id == session_id
                )
            ).order_by(TimeEntry.sequence_number).all()
            
            # Calculate total hours
            total_hours = 0
            if attendance_record.start_time and attendance_record.end_time:
                # Convert string times to datetime.time objects
                if isinstance(attendance_record.start_time, str):
                    start_time = datetime.strptime(attendance_record.start_time, '%H:%M:%S').time()
                else:
                    start_time = attendance_record.start_time
                    
                if isinstance(attendance_record.end_time, str):
                    end_time = datetime.strptime(attendance_record.end_time, '%H:%M:%S').time()
                else:
                    end_time = attendance_record.end_time
                    
                start_datetime = datetime.combine(date_obj, start_time)
                end_datetime = datetime.combine(date_obj, end_time)
                total_hours = (end_datetime - start_datetime).total_seconds() / 3600
            
            # Check if incomplete (has check-in but no check-out)
            has_incomplete = False
            current_pair = []
            for entry in time_entries:
                if entry.entry_type == 'check_in':
                    current_pair.append(entry)
                elif entry.entry_type == 'check_out' and current_pair:
                    current_pair.clear()
            if current_pair:
                has_incomplete = True
            
            # Build employee data
            employee_data = {
                'reg_id': attendance_record.reg_id,
                'first_name': attendance_record.first_name,
                'last_name': attendance_record.last_name,
                'occupation': attendance_record.occupation,
                'start_time': start_time.strftime('%H:%M') if attendance_record.start_time else '-',
                'end_time': end_time.strftime('%H:%M') if attendance_record.end_time else '-',
                'total_hours': round(total_hours, 2),
                'status': 'Incomplete' if has_incomplete else 'Complete',
                'sessions': len([e for e in time_entries if e.entry_type == 'check_out'])
            }
            
            # Apply filters
            if (show_present and not has_incomplete) or (show_incomplete and has_incomplete):
                attendance_data.append(employee_data)
        
        # Find absent employees
        absent_employees = []
        if show_absent:
            present_reg_ids = {emp['reg_id'] for emp in attendance_data}
            all_employees = Student_data.query.filter_by(session_code_id=session_id).all()
            
            for employee in all_employees:
                if employee.regid not in present_reg_ids and employee.regid not in [a.reg_id for a in attendance_records]:
                    absent_employees.append({
                        'reg_id': employee.regid,
                        'first_name': employee.first_name,
                        'last_name': employee.last_name,
                        'occupation': employee.occupation,
                        'start_time': '-',
                        'end_time': '-',
                        'total_hours': 0,
                        'status': 'Absent',
                        'sessions': 0
                    })
        
        # Combine all data
        all_data = attendance_data + absent_employees
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Employee Name', 'ID', 'Occupation', 'Status',
            'First In', 'Last Out', 'Total Hours', 'Sessions'
        ])
        
        for record in all_data:
            writer.writerow([
                f"{record['last_name']}, {record['first_name']}",
                record['reg_id'],
                record['occupation'],
                record['status'],
                record['start_time'],
                record['end_time'],
                f"{record['total_hours']}h",
                f"{record['sessions']} session{'s' if record['sessions'] != 1 else ''}"
            ])
        
        # Generate filename with date
        filename = f"daily_attendance_{selected_date}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logging.exception("Error generating daily attendance CSV: %s", str(e))
        flash("An error occurred while generating the CSV file.")
        return redirect(url_for('admin_bp.data', tab='attendance'))
