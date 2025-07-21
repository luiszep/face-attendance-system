"""
Local Session Code Management for Business Deployment

This module handles persistent session code storage for businesses.
Session codes are saved locally and persist across application restarts.
"""

import json
import os
from datetime import datetime


class SessionManager:
    def __init__(self, config_file='session_config.json'):
        """
        Initialize session manager with local config file.
        
        Args:
            config_file (str): Path to local session config file
        """
        self.config_file = os.path.join(os.path.dirname(__file__), '..', '..', config_file)
        self._ensure_config_exists()
        self._ensure_admin_credentials()
    
    def _ensure_config_exists(self):
        """Create config file if it doesn't exist."""
        if not os.path.exists(self.config_file):
            self._save_config({
                'session_code': None,
                'business_name': None,
                'setup_date': None,
                'last_updated': None,
                'admin_username': 'admin',
                'admin_password': 'admin123'
            })
    
    def _load_config(self):
        """Load configuration from local file."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[SESSION MANAGER] Error loading config: {e}")
            return {
                'session_code': None,
                'business_name': None,
                'setup_date': None,
                'last_updated': None
            }
    
    def _save_config(self, config):
        """Save configuration to local file."""
        try:
            config['last_updated'] = datetime.now().isoformat()
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"[SESSION MANAGER] Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"[SESSION MANAGER] Error saving config: {e}")
    
    def get_session_code(self):
        """
        Get the locally saved session code.
        
        Returns:
            str or None: Session code if exists, None if not configured
        """
        config = self._load_config()
        return config.get('session_code')
    
    def set_session_code(self, session_code, business_name=None):
        """
        Save session code locally for persistent use.
        
        Args:
            session_code (str): Session code to save
            business_name (str, optional): Business name for reference
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            config = self._load_config()
            
            # First time setup
            if not config.get('setup_date'):
                config['setup_date'] = datetime.now().isoformat()
            
            config['session_code'] = str(session_code)
            
            if business_name:
                config['business_name'] = business_name
            
            self._save_config(config)
            return True
            
        except Exception as e:
            print(f"[SESSION MANAGER] Error setting session code: {e}")
            return False
    
    def get_business_info(self):
        """
        Get business information from local config.
        
        Returns:
            dict: Business information including name, setup date, etc.
        """
        config = self._load_config()
        return {
            'session_code': config.get('session_code'),
            'business_name': config.get('business_name'),
            'setup_date': config.get('setup_date'),
            'last_updated': config.get('last_updated'),
            'is_configured': config.get('session_code') is not None
        }
    
    def clear_session_code(self):
        """
        Clear the saved session code (for testing or reset).
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            config = self._load_config()
            config['session_code'] = None
            config['business_name'] = None
            self._save_config(config)
            return True
        except Exception as e:
            print(f"[SESSION MANAGER] Error clearing session code: {e}")
            return False
    
    def is_configured(self):
        """
        Check if session code is already configured.
        
        Returns:
            bool: True if session code exists, False otherwise
        """
        session_code = self.get_session_code()
        return session_code is not None and session_code.strip() != ''
    
    def _ensure_admin_credentials(self):
        """Ensure admin credentials exist in config."""
        config = self._load_config()
        updated = False
        
        if 'admin_username' not in config:
            config['admin_username'] = 'admin'
            updated = True
            
        if 'admin_password' not in config:
            config['admin_password'] = 'admin123'
            updated = True
            
        if updated:
            self._save_config(config)
    
    def get_admin_credentials(self):
        """Get admin credentials from config."""
        config = self._load_config()
        return {
            'username': config.get('admin_username', 'admin'),
            'password': config.get('admin_password', 'admin123')
        }
    
    def update_admin_credentials(self, username=None, password=None):
        """Update admin credentials."""
        config = self._load_config()
        
        if username:
            config['admin_username'] = username
        if password:
            config['admin_password'] = password
            
        self._save_config(config)
        return True


# Global session manager instance
session_manager = SessionManager()