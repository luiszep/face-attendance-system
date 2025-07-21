import cv2
import face_recognition
import numpy as np
from datetime import datetime

# --- Allowed file extensions for uploads ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- Check if the uploaded file has an allowed extension ---
def allowed_file(filename):
    """
    Check if the uploaded file has an allowed image extension.
    Args:
        filename (str): The name of the uploaded file.
    Returns:
        bool: True if the file has an allowed extension, False otherwise.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Encode known student images ---
def findEncodings(imageslist):
    """
    Generate face encodings for a list of student images.
    Args:
        imageslist (list): List of images (as NumPy arrays).
    Returns:
        list: List of 128-dimension face encodings.
    """
    encodeList = []
    for img in imageslist:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert image to RGB (required by face_recognition)
        encode = face_recognition.face_encodings(img)[0]  # Get encoding for the first detected face
        encodeList.append(encode)
    return encodeList

# --- Compare incoming face with known encodings ---
def compare(encodeListKnown, encodeFace):
    """
    Compare an unknown face encoding with a list of known encodings.
    Args:
        encodeListKnown (list): Known face encodings.
        encodeFace (list): Encoding of the detected face.
    Returns:
        tuple:
            matches (list of bool): Whether each known encoding matches the input face.
            faceDis (list of float): Distances between known encodings and input.
            matchIndex (int): Index of the best match (lowest distance).
    """
    matches = face_recognition.compare_faces(encodeListKnown, encodeFace, tolerance=0.5)
    faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
    matchIndex = np.argmin(faceDis)  # Index of best match
    return matches, faceDis, matchIndex

# --- Get student ID from a successful match ---
def get_data(matches, matchIndex, studentIds):
    """
    Retrieve student ID if a valid face match is found.
    Args:
        matches (list): Boolean list indicating match status.
        matchIndex (int): Index of the closest match.
        studentIds (list): List of student IDs corresponding to known encodings.
    Returns:
        str or None: The matched student ID or None if no valid match.
    """
    if matches[matchIndex]:
        return studentIds[matchIndex]
    return None

# --- Retrieve student information from the database ---
def mysqlconnect(student_id, session_code_id):
    """
    Fetch detailed student information from the database 
    based on student ID and session code.
    Args:
        student_id (str): The recognized student's ID.
        session_code_id (int): The associated session code.
    Returns:
        tuple: (id, first_name, last_name, occupation, regular_wage, 
        overtime_wage, regular_hours, maximum_overtime_hours)

    """
    from backend.app import app
    from backend.models import Student_data
    if student_id is None:
        return (None,)*8
    try:
        with app.app_context():
            student_data = Student_data.query.filter_by(
                regid=student_id,
                session_code_id=session_code_id
            ).first()
            if student_data:
                return (
                    student_data.id,
                    student_data.first_name,
                    student_data.last_name,
                    student_data.occupation,
                    student_data.regular_wage,
                    student_data.overtime_wage,
                    student_data.regular_hours,
                    student_data.maximum_overtime_hours
                )
            else:
                return (None,)*8
    except Exception as e:
        print("Error fetching student data:", e)
        return (None,)*8

# --- Record or update attendance entry (PARALLEL SYSTEM) ---
def record_attendance(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id):
    """
    PARALLEL SYSTEM: Record attendance using both old and new systems simultaneously.
    This allows safe testing of the new multi-session system alongside the existing system.
    
    Args:
        first_name (str): First name of the employee.
        last_name (str): Last name of the employee.
        occupation (str): Job title or role.
        regular_wage (float): Hourly wage at the time of attendance.
        current_date (date): The date of attendance.
        reg_id (str): Unique registration ID of the employee.
        session_code_id (int): ID of the active session code.
    """
    from backend.app import app
    from backend.models import db, Attendance
    
    print(f"[PARALLEL] Processing attendance for {first_name} {last_name} (reg_id: {reg_id})")
    
    # Run both systems in parallel - but ensure each system only processes ONCE per camera detection
    old_system_success = record_attendance_old_system(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id)
    
    # NEW SYSTEM: Only call once per actual camera detection
    # The issue was calling record_time_entry() multiple times per detection
    new_system_success = record_time_entry(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id)
    
    # Log results for monitoring
    print(f"[PARALLEL] Old system: {'SUCCESS' if old_system_success else 'FAILED'}")
    print(f"[PARALLEL] New system: {'SUCCESS' if new_system_success else 'FAILED'}")
    
    # For now, we rely on the old system for production stability
    # but collect data from both systems for comparison
    if old_system_success and new_system_success:
        print(f"[PARALLEL] Both systems recorded successfully")
    elif old_system_success:
        print(f"[PARALLEL] Old system succeeded, new system failed - using old system result")
    elif new_system_success:
        print(f"[PARALLEL] New system succeeded, old system failed - WARNING: investigate old system")
    else:
        print(f"[PARALLEL] Both systems failed - CRITICAL ERROR")


def record_attendance_old_system(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id):
    """
    Original attendance recording logic (preserved for parallel testing).
    Records single start/end time per day with continuous end time updates.
    """
    from backend.app import app
    from backend.models import db, Attendance
    try:
        with app.app_context():
            # Check if an attendance entry already exists for this student on this date/session
            existing_entry = Attendance.query.filter_by(
                reg_id=reg_id,
                date=current_date,
                session_code_id=session_code_id
            ).first()
            current_time_str = datetime.now().strftime("%H:%M:%S")
            if existing_entry:
                # Update end time if entry exists
                existing_entry.end_time = current_time_str
                db.session.commit()
                print("[OLD SYSTEM] Attendance end time updated.")
                return True
            else:
                # Create a new attendance record
                new_attendance = Attendance(
                    first_name=first_name,
                    last_name=last_name,
                    occupation=occupation,
                    regular_wage=regular_wage,
                    start_time=current_time_str,
                    end_time=current_time_str,
                    date=current_date,
                    reg_id=reg_id,
                    session_code_id=session_code_id
                )
                db.session.add(new_attendance)
                db.session.commit()
                print(f"[OLD SYSTEM] Attendance recorded for {first_name} {last_name} (reg_id: {reg_id}) in session {session_code_id}.")
                print("[OLD SYSTEM] Start and end time initialized (first entry).")
                return True
    except Exception as e:
        print(f"[OLD SYSTEM ERROR] Failed to record attendance: {e}")
        return False


# --- NEW MULTI-SESSION ATTENDANCE FUNCTIONS ---

def get_employee_current_status(reg_id, session_code_id, current_date):
    """
    Determine if employee should check-in or check-out based on their last entry.
    
    Args:
        reg_id (str): Employee registration ID
        session_code_id (int): Session code ID  
        current_date (date): Current date
        
    Returns:
        tuple: (next_action, sequence_number)
            next_action: 'check_in' or 'check_out'
            sequence_number: Next sequence number to use
    """
    from backend.app import app
    from backend.models import TimeEntry
    
    try:
        with app.app_context():
            # Get the latest entry for this employee today
            latest_entry = TimeEntry.query.filter_by(
                reg_id=reg_id,
                session_code_id=session_code_id,
                date=current_date
            ).order_by(TimeEntry.timestamp.desc()).first()
            
            if not latest_entry:
                # No entries today - should check in with sequence 1
                return 'check_in', 1
            elif latest_entry.entry_type == 'check_out':
                # Last action was check out - should check in with next sequence
                return 'check_in', latest_entry.sequence_number + 1
            else:  # latest_entry.entry_type == 'check_in'
                # Last action was check in - should check out with same sequence
                return 'check_out', latest_entry.sequence_number
                
    except Exception as e:
        print(f"[ERROR] Failed to get employee status: {e}")
        return 'check_in', 1  # Default fallback


# Global variable to track last scan results for the simple UI
last_scan_results = {}

def record_time_entry(first_name, last_name, occupation, regular_wage, current_date, reg_id, session_code_id):
    """
    Record a new time entry (check-in or check-out) for multi-session attendance tracking.
    Thread-safe implementation to handle concurrent camera detection calls.
    
    Args:
        first_name (str): Employee first name
        last_name (str): Employee last name  
        occupation (str): Job title
        regular_wage (float): Hourly wage
        current_date (date): Date of entry
        reg_id (str): Employee registration ID
        session_code_id (int): Session code ID
    """
    from backend.app import app
    from backend.models import db, TimeEntry
    from datetime import datetime, timedelta
    import threading
    import time
    
    # Thread-safe lock per employee to prevent concurrent processing
    if not hasattr(record_time_entry, 'locks'):
        record_time_entry.locks = {}
    
    lock_key = f"{reg_id}_{session_code_id}_{current_date}"
    if lock_key not in record_time_entry.locks:
        record_time_entry.locks[lock_key] = threading.Lock()
    
    # Only one thread can process this employee at a time
    with record_time_entry.locks[lock_key]:
        try:
            with app.app_context():
                current_time = datetime.now()
                
                # Extended deduplication check - 60 seconds to handle camera stream bursts
                recent_entry = TimeEntry.query.filter_by(
                    reg_id=reg_id,
                    session_code_id=session_code_id,
                    date=current_date
                ).filter(
                    TimeEntry.timestamp >= current_time - timedelta(seconds=60)
                ).order_by(TimeEntry.timestamp.desc()).first()
                
                if recent_entry:
                    time_diff = (current_time - recent_entry.timestamp).total_seconds()
                    print(f"[NEW SYSTEM] Blocked - entry exists from {time_diff:.1f}s ago ({recent_entry.entry_type}#{recent_entry.sequence_number})")
                    
                    # Store result for simple UI
                    last_scan_results[reg_id] = {
                        'result': 'blocked',
                        'message': f"{first_name} {last_name} ({reg_id}) - No time recorded (too soon after last scan)",
                        'timestamp': current_time,
                        'employee_recognized': True
                    }
                    return True
                
                # Get employee status for next action
                action, sequence_num = get_employee_current_status(reg_id, session_code_id, current_date)
                
                # Final safety check for exact duplicates
                existing_duplicate = TimeEntry.query.filter_by(
                    reg_id=reg_id,
                    session_code_id=session_code_id,
                    date=current_date,
                    sequence_number=sequence_num,
                    entry_type=action
                ).first()
                
                if existing_duplicate:
                    print(f"[NEW SYSTEM] Blocked - exact duplicate {action}#{sequence_num} exists")
                    
                    # Store result for simple UI
                    last_scan_results[reg_id] = {
                        'result': 'blocked',
                        'message': f"{first_name} {last_name} ({reg_id}) - No time recorded (duplicate entry)",
                        'timestamp': current_time,
                        'employee_recognized': True
                    }
                    return True
                
                # Create and save new entry
                new_entry = TimeEntry(
                    reg_id=reg_id,
                    session_code_id=session_code_id,
                    timestamp=current_time,
                    entry_type=action,
                    date=current_date,
                    sequence_number=sequence_num,
                    first_name=first_name,
                    last_name=last_name,
                    occupation=occupation,
                    regular_wage=regular_wage
                )
                
                db.session.add(new_entry)
                db.session.commit()
                
                print(f"[NEW SYSTEM] SUCCESS: {action.upper()}#{sequence_num} for {first_name} {last_name}")
                
                # Store result for simple UI
                action_text = "Check in" if action == 'check_in' else "Check out"
                last_scan_results[reg_id] = {
                    'result': 'success',
                    'message': f"{first_name} {last_name} ({reg_id}) - {action_text} time recorded",
                    'action': action,
                    'sequence': sequence_num,
                    'timestamp': current_time,
                    'employee_recognized': True
                }
                
                return True
                
        except Exception as e:
            print(f"[NEW SYSTEM ERROR] {e}")
            try:
                db.session.rollback()
            except:
                pass
            
            # Store error result for simple UI
            last_scan_results[reg_id] = {
                'result': 'error',
                'message': f"{first_name} {last_name} ({reg_id}) - Error recording time",
                'timestamp': datetime.now(),
                'employee_recognized': True
            }
            return False


def get_daily_time_summary(reg_id, session_code_id, target_date):
    """
    Get a summary of all time entries for an employee on a specific date.
    
    Args:
        reg_id (str): Employee registration ID
        session_code_id (int): Session code ID
        target_date (date): Date to summarize
        
    Returns:
        dict: Summary with total hours and session details
    """
    from backend.app import app
    from backend.models import TimeEntry
    
    try:
        with app.app_context():
            entries = TimeEntry.query.filter_by(
                reg_id=reg_id,
                session_code_id=session_code_id,
                date=target_date
            ).order_by(TimeEntry.timestamp.asc()).all()
            
            if not entries:
                return {'total_hours': 0, 'sessions': [], 'status': 'no_entries'}
            
            # Group entries into check-in/check-out pairs
            sessions = []
            current_session = None
            total_minutes = 0
            
            for entry in entries:
                if entry.entry_type == 'check_in':
                    current_session = {
                        'sequence': entry.sequence_number,
                        'check_in': entry.timestamp,
                        'check_out': None,
                        'duration_minutes': 0
                    }
                    sessions.append(current_session)
                elif entry.entry_type == 'check_out' and current_session:
                    current_session['check_out'] = entry.timestamp
                    duration = (entry.timestamp - current_session['check_in']).total_seconds() / 60
                    current_session['duration_minutes'] = round(duration, 2)
                    total_minutes += duration
            
            # Determine current status
            last_entry = entries[-1]
            status = 'checked_in' if last_entry.entry_type == 'check_in' else 'checked_out'
            
            return {
                'total_hours': round(total_minutes / 60, 2),
                'sessions': sessions,
                'status': status,
                'last_action': last_entry.entry_type,
                'next_sequence': last_entry.sequence_number + (1 if status == 'checked_out' else 0)
            }
            
    except Exception as e:
        print(f"[ERROR] Failed to get daily summary: {e}")
        return {'total_hours': 0, 'sessions': [], 'status': 'error'}


# --- TIME FORMATTING UTILITIES ---

def format_time_display(total_hours):
    """
    Format time for display: minutes first, then hours when > 60 minutes.
    
    Args:
        total_hours (float): Time in hours
        
    Returns:
        str: Formatted time string (e.g., "45min" or "2.5h")
    """
    if total_hours == 0:
        return "0min"
    
    total_minutes = total_hours * 60
    
    if total_minutes < 60:
        return f"{round(total_minutes)}min"
    else:
        return f"{total_hours:.1f}h"


# --- PARALLEL SYSTEM COMPARISON FUNCTIONS ---

def compare_system_results(reg_id, session_code_id, target_date):
    """
    Compare results between old and new attendance systems for validation.
    
    Args:
        reg_id (str): Employee registration ID
        session_code_id (int): Session code ID
        target_date (date): Date to compare
        
    Returns:
        dict: Comparison results and discrepancies
    """
    from backend.app import app
    from backend.models import Attendance, TimeEntry
    
    try:
        with app.app_context():
            # Get old system data
            old_entry = Attendance.query.filter_by(
                reg_id=reg_id,
                session_code_id=session_code_id,
                date=target_date
            ).first()
            
            # Get new system data
            new_summary = get_daily_time_summary(reg_id, session_code_id, target_date)
            
            comparison = {
                'date': target_date,
                'employee': reg_id,
                'old_system': {},
                'new_system': new_summary,
                'discrepancies': []
            }
            
            if old_entry:
                # Parse old system times
                from datetime import datetime, timedelta
                try:
                    start_time = datetime.strptime(old_entry.start_time, "%H:%M:%S").time()
                    end_time = datetime.strptime(old_entry.end_time, "%H:%M:%S").time()
                    
                    # Calculate total hours (simple difference)
                    start_datetime = datetime.combine(target_date, start_time)
                    end_datetime = datetime.combine(target_date, end_time)
                    
                    if end_datetime < start_datetime:  # Handle midnight rollover
                        end_datetime += timedelta(days=1)
                    
                    total_seconds = (end_datetime - start_datetime).total_seconds()
                    old_total_hours = round(total_seconds / 3600, 2)
                    
                    comparison['old_system'] = {
                        'start_time': old_entry.start_time,
                        'end_time': old_entry.end_time,
                        'total_hours': old_total_hours,
                        'status': 'single_session'
                    }
                except Exception as e:
                    comparison['old_system'] = {
                        'error': f"Failed to parse times: {e}",
                        'raw_start': old_entry.start_time,
                        'raw_end': old_entry.end_time
                    }
            else:
                comparison['old_system'] = {'status': 'no_entry'}
            
            # Compare results
            if old_entry and new_summary['sessions']:
                old_hours = comparison['old_system'].get('total_hours', 0)
                new_hours = new_summary.get('total_hours', 0)
                hour_difference = abs(old_hours - new_hours)
                
                if hour_difference > 0.1:  # Allow 6-minute tolerance
                    comparison['discrepancies'].append({
                        'type': 'total_hours_mismatch',
                        'old_hours': old_hours,
                        'new_hours': new_hours,
                        'difference': hour_difference
                    })
                
                # Check session count logic
                if new_summary['sessions']:
                    first_session = new_summary['sessions'][0]
                    last_session = new_summary['sessions'][-1]
                    
                    # Old system should match first check-in to last check-out
                    if first_session.get('check_in') and last_session.get('check_out'):
                        new_start = first_session['check_in'].strftime("%H:%M:%S")
                        new_end = last_session['check_out'].strftime("%H:%M:%S")
                        
                        if (comparison['old_system'].get('start_time') != new_start or 
                            comparison['old_system'].get('end_time') != new_end):
                            comparison['discrepancies'].append({
                                'type': 'time_boundaries_mismatch',
                                'old_start': comparison['old_system'].get('start_time'),
                                'old_end': comparison['old_system'].get('end_time'),
                                'new_start': new_start,
                                'new_end': new_end
                            })
            
            return comparison
            
    except Exception as e:
        return {
            'error': f"Comparison failed: {e}",
            'date': target_date,
            'employee': reg_id
        }


def generate_daily_comparison_report(session_code_id, target_date):
    """
    Generate a comprehensive comparison report for all employees on a given date.
    
    Args:
        session_code_id (int): Session code ID
        target_date (date): Date to analyze
        
    Returns:
        dict: Full comparison report
    """
    from backend.app import app
    from backend.models import Student_data
    
    try:
        with app.app_context():
            # Get all employees for this session
            employees = Student_data.query.filter_by(session_code_id=session_code_id).all()
            
            report = {
                'date': target_date,
                'session_id': session_code_id,
                'total_employees': len(employees),
                'comparisons': [],
                'summary': {
                    'both_systems_agree': 0,
                    'discrepancies_found': 0,
                    'old_only': 0,
                    'new_only': 0,
                    'neither_system': 0
                }
            }
            
            for employee in employees:
                comparison = compare_system_results(employee.regid, session_code_id, target_date)
                report['comparisons'].append(comparison)
                
                # Update summary
                old_has_data = comparison['old_system'].get('status') != 'no_entry'
                new_has_data = comparison['new_system'].get('status') != 'no_entries'
                has_discrepancies = len(comparison.get('discrepancies', [])) > 0
                
                if old_has_data and new_has_data:
                    if has_discrepancies:
                        report['summary']['discrepancies_found'] += 1
                    else:
                        report['summary']['both_systems_agree'] += 1
                elif old_has_data:
                    report['summary']['old_only'] += 1
                elif new_has_data:
                    report['summary']['new_only'] += 1
                else:
                    report['summary']['neither_system'] += 1
            
            return report
            
    except Exception as e:
        return {
            'error': f"Report generation failed: {e}",
            'date': target_date,
            'session_id': session_code_id
        }
