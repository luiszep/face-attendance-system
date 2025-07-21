#!/usr/bin/env python3
"""
Clean up duplicate TimeEntry records to test the fixed system.
"""

import sys
import os
from datetime import date

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app
from backend.models import db, TimeEntry

def cleanup_duplicates():
    """Remove all TimeEntry records for today to start fresh."""
    
    with app.app_context():
        today = date.today()
        
        # Delete all time entries for today
        deleted_count = TimeEntry.query.filter_by(date=today).delete()
        db.session.commit()
        
        print(f"Cleaned up {deleted_count} TimeEntry records for {today}")
        print("System ready for fresh testing")

if __name__ == '__main__':
    cleanup_duplicates()