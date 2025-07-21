#!/usr/bin/env python3
"""
Test script for the parallel attendance tracking system.
This validates that both old and new systems work together correctly.
"""

import sys
import os
from datetime import datetime, date
import time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app
from backend.models import db, TimeEntry, Attendance
from backend.utils.helpers import (
    record_attendance,
    compare_system_results,
    get_daily_time_summary
)

def test_parallel_system():
    """Test both systems running in parallel."""
    
    with app.app_context():
        print("Testing Parallel Attendance System")
        print("=" * 50)
        
        # Test data
        test_employee = {
            'reg_id': 'PARALLEL001',
            'session_code_id': 1,
            'first_name': 'Jane',
            'last_name': 'Smith', 
            'occupation': 'Marketing Manager',
            'regular_wage': 28.75
        }
        
        today = date.today()
        
        # Clean up any existing test data
        TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        
        Attendance.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        
        db.session.commit()
        print(f"Cleaned up existing test data for {test_employee['reg_id']}")
        
        # Test 1: First detection (both systems should create initial records)
        print(f"\nTest 1: First detection - both systems create records")
        record_attendance(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        
        # Brief delay to see timestamps
        time.sleep(2)
        
        # Test 2: Second detection (old system updates, new system creates check-out)
        print(f"\nTest 2: Second detection - old updates end time, new creates check-out")
        record_attendance(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        
        time.sleep(2)
        
        # Test 3: Third detection (lunch return - new system creates check-in #2)
        print(f"\nTest 3: Third detection - lunch return")
        record_attendance(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        
        time.sleep(2)
        
        # Test 4: Final detection (end of day)
        print(f"\nTest 4: Final detection - end of day")
        record_attendance(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        
        # Test 5: Compare results
        print(f"\nTest 5: Comparing system results")
        comparison = compare_system_results(
            test_employee['reg_id'], 
            test_employee['session_code_id'], 
            today
        )
        
        print("=" * 30)
        print("COMPARISON RESULTS:")
        print("=" * 30)
        
        # Old system results
        print("OLD SYSTEM:")
        old_sys = comparison['old_system']
        if old_sys.get('status') == 'no_entry':
            print("   No entry found")
        else:
            print(f"   Start Time: {old_sys.get('start_time', 'N/A')}")
            print(f"   End Time: {old_sys.get('end_time', 'N/A')}")
            print(f"   Total Hours: {old_sys.get('total_hours', 'N/A')}")
            
        # New system results
        print("\nNEW SYSTEM:")
        new_sys = comparison['new_system']
        print(f"   Status: {new_sys.get('status', 'N/A')}")
        print(f"   Total Hours: {new_sys.get('total_hours', 'N/A')}")
        print(f"   Sessions: {len(new_sys.get('sessions', []))}")
        
        for i, session in enumerate(new_sys.get('sessions', []), 1):
            check_in = session.get('check_in', 'N/A')
            check_out = session.get('check_out', 'N/A')
            duration = session.get('duration_minutes', 'N/A')
            print(f"   Session {session.get('sequence', i)}: {check_in} -> {check_out} ({duration} min)")
        
        # Discrepancies
        print(f"\nDISCREPANCIES:")
        discrepancies = comparison.get('discrepancies', [])
        if not discrepancies:
            print("   None found - systems are consistent!")
        else:
            for disc in discrepancies:
                print(f"   {disc['type']}: {disc}")
        
        # Test 6: Verify database states
        print(f"\nTest 6: Database verification")
        
        # Check old system table
        old_entries = Attendance.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).all()
        
        print(f"Old system entries: {len(old_entries)}")
        for entry in old_entries:
            print(f"   {entry.start_time} -> {entry.end_time}")
        
        # Check new system table
        new_entries = TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).order_by(TimeEntry.timestamp.asc()).all()
        
        print(f"New system entries: {len(new_entries)}")
        for entry in new_entries:
            print(f"   {entry.entry_type} #{entry.sequence_number} at {entry.timestamp}")
        
        print(f"\nParallel system test completed!")
        
        # Clean up test data
        TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        
        Attendance.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        
        db.session.commit()
        print(f"Test data cleaned up")

if __name__ == '__main__':
    try:
        test_parallel_system()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)