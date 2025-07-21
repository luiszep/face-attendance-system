#!/usr/bin/env python3
"""
Test script for the new multi-session attendance tracking system.
This validates the TimeEntry model and helper functions.
"""

import sys
import os
from datetime import datetime, date

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app
from backend.models import db, TimeEntry
from backend.utils.helpers import (
    get_employee_current_status,
    record_time_entry, 
    get_daily_time_summary
)

def test_multi_session_system():
    """Test the complete multi-session workflow."""
    
    with app.app_context():
        print("Testing Multi-Session Attendance System")
        print("=" * 50)
        
        # Test data
        test_employee = {
            'reg_id': 'TEST001',
            'session_code_id': 1,
            'first_name': 'John',
            'last_name': 'Doe', 
            'occupation': 'Software Engineer',
            'regular_wage': 25.50
        }
        
        today = date.today()
        
        # Clean up any existing test data
        TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        db.session.commit()
        
        print(f"Cleaned up existing test data for {test_employee['reg_id']}")
        
        # Test 1: First check-in of the day
        print(f"\nTest 1: First check-in")
        status, seq = get_employee_current_status(
            test_employee['reg_id'], 
            test_employee['session_code_id'], 
            today
        )
        print(f"   Status: {status}, Sequence: {seq}")
        assert status == 'check_in' and seq == 1, f"Expected ('check_in', 1), got ({status}, {seq})"
        
        # Record the check-in
        success = record_time_entry(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        assert success, "Failed to record first check-in"
        print("   SUCCESS: First check-in recorded successfully")
        
        # Test 2: After check-in, should be check-out
        print(f"\nTest 2: After check-in -> should be check-out")
        status, seq = get_employee_current_status(
            test_employee['reg_id'], 
            test_employee['session_code_id'], 
            today
        )
        print(f"   Status: {status}, Sequence: {seq}")
        assert status == 'check_out' and seq == 1, f"Expected ('check_out', 1), got ({status}, {seq})"
        
        # Record first check-out (lunch break)
        success = record_time_entry(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        assert success, "Failed to record first check-out"
        print("   SUCCESS: First check-out recorded successfully")
        
        # Test 3: After check-out, should be check-in with sequence 2
        print(f"\nTest 3: After check-out -> should be check-in #2")
        status, seq = get_employee_current_status(
            test_employee['reg_id'], 
            test_employee['session_code_id'], 
            today
        )
        print(f"   Status: {status}, Sequence: {seq}")
        assert status == 'check_in' and seq == 2, f"Expected ('check_in', 2), got ({status}, {seq})"
        
        # Record second check-in (back from lunch)
        success = record_time_entry(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        assert success, "Failed to record second check-in"
        print("   SUCCESS: Second check-in recorded successfully")
        
        # Record final check-out
        success = record_time_entry(
            test_employee['first_name'],
            test_employee['last_name'],
            test_employee['occupation'],
            test_employee['regular_wage'],
            today,
            test_employee['reg_id'],
            test_employee['session_code_id']
        )
        assert success, "Failed to record final check-out"
        print("   SUCCESS: Final check-out recorded successfully")
        
        # Test 4: Get daily summary
        print(f"\nTest 4: Daily time summary")
        summary = get_daily_time_summary(
            test_employee['reg_id'], 
            test_employee['session_code_id'], 
            today
        )
        
        print(f"   Total Hours: {summary['total_hours']}")
        print(f"   Status: {summary['status']}")
        print(f"   Sessions: {len(summary['sessions'])}")
        
        for i, session in enumerate(summary['sessions'], 1):
            print(f"   Session {session['sequence']}: {session['check_in']} -> {session['check_out']} ({session['duration_minutes']} min)")
        
        assert len(summary['sessions']) == 2, f"Expected 2 sessions, got {len(summary['sessions'])}"
        assert summary['status'] == 'checked_out', f"Expected 'checked_out', got {summary['status']}"
        print("   SUCCESS: Daily summary looks correct")
        
        # Test 5: Verify database entries
        print(f"\nTest 5: Database integrity check")
        entries = TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).order_by(TimeEntry.timestamp.asc()).all()
        
        print(f"   Total entries: {len(entries)}")
        expected_pattern = ['check_in', 'check_out', 'check_in', 'check_out']
        actual_pattern = [entry.entry_type for entry in entries]
        
        print(f"   Expected pattern: {expected_pattern}")
        print(f"   Actual pattern:   {actual_pattern}")
        
        assert actual_pattern == expected_pattern, f"Pattern mismatch: {actual_pattern}"
        print("   SUCCESS: Database entries match expected pattern")
        
        print(f"\nALL TESTS PASSED! Multi-session system is working correctly.")
        
        # Clean up test data
        TimeEntry.query.filter_by(
            reg_id=test_employee['reg_id'],
            session_code_id=test_employee['session_code_id'],
            date=today
        ).delete()
        db.session.commit()
        print(f"Test data cleaned up")

if __name__ == '__main__':
    try:
        test_multi_session_system()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)