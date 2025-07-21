#!/usr/bin/env python3
"""
Real-time monitoring script for the parallel attendance system.
Run this during employee testing to track both systems.
"""

import sys
import os
from datetime import datetime, date
import time
import json

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app
from backend.models import db, TimeEntry, Attendance, Student_data
from backend.utils.helpers import (
    compare_system_results,
    generate_daily_comparison_report,
    get_daily_time_summary
)

def monitor_attendance_activity(session_code_id, monitor_date=None):
    """
    Monitor real-time attendance activity for both systems.
    
    Args:
        session_code_id (int): Session to monitor
        monitor_date (date): Date to monitor (default: today)
    """
    if monitor_date is None:
        monitor_date = date.today()
    
    with app.app_context():
        print(f"Real-Time Attendance Monitoring")
        print(f"Session ID: {session_code_id}")
        print(f"Date: {monitor_date}")
        print("=" * 60)
        
        # Get all employees for context
        employees = Student_data.query.filter_by(session_code_id=session_code_id).all()
        employee_names = {emp.regid: f"{emp.first_name} {emp.last_name}" for emp in employees}
        
        print(f"Monitoring {len(employees)} employees:")
        for reg_id, name in employee_names.items():
            print(f"  - {reg_id}: {name}")
        print()
        
        last_old_count = 0
        last_new_count = 0
        
        try:
            while True:
                # Count current entries
                old_entries = Attendance.query.filter_by(
                    session_code_id=session_code_id,
                    date=monitor_date
                ).count()
                
                new_entries = TimeEntry.query.filter_by(
                    session_code_id=session_code_id,
                    date=monitor_date
                ).count()
                
                # Show updates only when counts change
                if old_entries != last_old_count or new_entries != last_new_count:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Activity detected!")
                    print(f"  Old system entries: {old_entries} (+{old_entries - last_old_count})")
                    print(f"  New system entries: {new_entries} (+{new_entries - last_new_count})")
                    
                    # Show recent new system activities
                    if new_entries > last_new_count:
                        recent_entries = TimeEntry.query.filter_by(
                            session_code_id=session_code_id,
                            date=monitor_date
                        ).order_by(TimeEntry.timestamp.desc()).limit(5).all()
                        
                        print(f"  Recent activities:")
                        for entry in reversed(recent_entries[-5:]):  # Show in chronological order
                            employee_name = employee_names.get(entry.reg_id, entry.reg_id)
                            timestamp = entry.timestamp.strftime('%H:%M:%S')
                            print(f"    {timestamp}: {employee_name} - {entry.entry_type.upper()} #{entry.sequence_number}")
                    
                    print()
                    
                    last_old_count = old_entries
                    last_new_count = new_entries
                
                time.sleep(2)  # Check every 2 seconds
                
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped by user")
            
        # Generate final summary
        print(f"\nFinal Summary for {monitor_date}:")
        print("=" * 40)
        
        report = generate_daily_comparison_report(session_code_id, monitor_date)
        
        if 'error' in report:
            print(f"Error generating report: {report['error']}")
        else:
            summary = report['summary']
            print(f"Total employees checked: {summary['both_systems_agree'] + summary['discrepancies_found']}")
            print(f"Systems agree: {summary['both_systems_agree']}")
            print(f"Discrepancies found: {summary['discrepancies_found']}")
            print(f"Old system only: {summary['old_only']}")
            print(f"New system only: {summary['new_only']}")
            
            if summary['discrepancies_found'] > 0:
                print(f"\nDiscrepancy Details:")
                for comparison in report['comparisons']:
                    if comparison.get('discrepancies'):
                        employee_name = employee_names.get(comparison['employee'], comparison['employee'])
                        print(f"  {employee_name} ({comparison['employee']}):")
                        for disc in comparison['discrepancies']:
                            print(f"    - {disc['type']}: {disc}")


def check_employee_status(session_code_id, reg_id=None):
    """
    Check current status of specific employee or all employees.
    """
    today = date.today()
    
    with app.app_context():
        if reg_id:
            employees = Student_data.query.filter_by(
                session_code_id=session_code_id, 
                regid=reg_id
            ).all()
        else:
            employees = Student_data.query.filter_by(session_code_id=session_code_id).all()
        
        print(f"Employee Status Check - {today}")
        print("=" * 50)
        
        for employee in employees:
            print(f"\n{employee.first_name} {employee.last_name} ({employee.regid}):")
            
            # Get new system summary
            summary = get_daily_time_summary(employee.regid, session_code_id, today)
            
            if summary['status'] == 'no_entries':
                print("  Status: No activity today")
            else:
                print(f"  Status: Currently {summary['status']}")
                print(f"  Total hours: {summary['total_hours']}")
                print(f"  Sessions: {len(summary['sessions'])}")
                
                for session in summary['sessions']:
                    check_in = session['check_in'].strftime('%H:%M:%S') if session['check_in'] else 'N/A'
                    check_out = session['check_out'].strftime('%H:%M:%S') if session['check_out'] else 'Still active'
                    duration = f"{session['duration_minutes']} min" if session['check_out'] else "In progress"
                    print(f"    Session {session['sequence']}: {check_in} -> {check_out} ({duration})")


def export_comparison_report(session_code_id, target_date=None, filename=None):
    """
    Export detailed comparison report to JSON file.
    """
    if target_date is None:
        target_date = date.today()
    
    if filename is None:
        filename = f"attendance_comparison_{session_code_id}_{target_date.strftime('%Y%m%d')}.json"
    
    with app.app_context():
        report = generate_daily_comparison_report(session_code_id, target_date)
        
        # Convert date objects to strings for JSON serialization
        def serialize_dates(obj):
            if isinstance(obj, date):
                return obj.strftime('%Y-%m-%d')
            elif isinstance(obj, datetime):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            return obj
        
        # Deep convert dates
        def convert_dates(obj):
            if isinstance(obj, dict):
                return {k: convert_dates(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_dates(v) for v in obj]
            else:
                return serialize_dates(obj)
        
        serializable_report = convert_dates(report)
        
        with open(filename, 'w') as f:
            json.dump(serializable_report, f, indent=2)
        
        print(f"Comparison report exported to: {filename}")
        return filename


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Monitor real-time: python monitor_parallel_system.py monitor <session_id>")
        print("  Check status: python monitor_parallel_system.py status <session_id> [employee_id]")
        print("  Export report: python monitor_parallel_system.py export <session_id> [date_YYYYMMDD]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'monitor' and len(sys.argv) >= 3:
        session_id = int(sys.argv[2])
        monitor_attendance_activity(session_id)
        
    elif command == 'status' and len(sys.argv) >= 3:
        session_id = int(sys.argv[2])
        employee_id = sys.argv[3] if len(sys.argv) > 3 else None
        check_employee_status(session_id, employee_id)
        
    elif command == 'export' and len(sys.argv) >= 3:
        session_id = int(sys.argv[2])
        target_date = None
        if len(sys.argv) > 3:
            date_str = sys.argv[3]
            target_date = datetime.strptime(date_str, '%Y%m%d').date()
        
        export_comparison_report(session_id, target_date)
        
    else:
        print("Invalid command or arguments")
        sys.exit(1)