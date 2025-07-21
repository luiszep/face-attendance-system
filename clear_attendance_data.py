#!/usr/bin/env python3
"""
Clear all attendance and time_entries data for fresh testing.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app
from backend.models import db, Attendance, TimeEntry

def clear_attendance_data():
    """Clear all attendance and time_entries records."""
    
    with app.app_context():
        try:
            # Delete all time entries
            time_entries_count = TimeEntry.query.count()
            TimeEntry.query.delete()
            
            # Delete all attendance records
            attendance_count = Attendance.query.count()
            Attendance.query.delete()
            
            # Commit the changes
            db.session.commit()
            
            print(f"Successfully cleared:")
            print(f"   - {attendance_count} Attendance records")
            print(f"   - {time_entries_count} TimeEntry records")
            print(f"\nDatabase is now clean and ready for testing!")
            
        except Exception as e:
            print(f"Error clearing data: {e}")
            db.session.rollback()

if __name__ == '__main__':
    print("Clearing all attendance data...")
    clear_attendance_data()