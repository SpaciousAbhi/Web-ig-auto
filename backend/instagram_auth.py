"""
Instagram Authentication and Session Management
Handles secure authentication with Instagram accounts using instagrapi
"""
import os
import json
import logging
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, LoginRequired, ChallengeRequired,
    FeedbackRequired, PleaseWaitFewMinutes
)
from typing import Optional

class InstagramAuthenticator:
    def __init__(self, username: str, password: str, session_dir: str = "sessions"):
        self.username = username
        self.password = password
        self.session_dir = Path(session_dir)
        self.session_file = self.session_dir / f"{username}_session.json"
        self.client = Client()
        self.logger = logging.getLogger(f"auth.{username}")
        
        # Create session directory if it doesn't exist
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
    def authenticate(self) -> bool:
        """
        Authenticate with Instagram using session management best practices
        """
        try:
            # Attempt to load existing session first
            if self._load_session():
                if self._validate_session():
                    self.logger.info(f"Successfully authenticated {self.username} using existing session")
                    return True
                else:
                    self.logger.info(f"Existing session for {self.username} is invalid, performing fresh login")
            
            # Perform fresh authentication
            return self._fresh_login()
            
        except Exception as e:
            self.logger.error(f"Authentication failed for {self.username}: {str(e)}")
            return False
    
    def _load_session(self) -> bool:
        """Load existing session data"""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                self.client.set_settings(session_data)
                return True
        except Exception as e:
            self.logger.warning(f"Failed to load session for {self.username}: {str(e)}")
        return False
    
    def _validate_session(self) -> bool:
        """Validate current session by making a test request"""
        try:
            self.client.get_timeline_feed()
            return True
        except LoginRequired:
            self.logger.info(f"Session validation failed - login required for {self.username}")
        except Exception as e:
            self.logger.warning(f"Session validation error for {self.username}: {str(e)}")
        return False
    
    def _fresh_login(self) -> bool:
        """Perform fresh login and save session"""
        try:
            self.client.login(self.username, self.password)
            self._save_session()
            self.logger.info(f"Fresh login successful for {self.username}")
            return True
        except BadPassword:
            self.logger.error(f"Invalid credentials for {self.username}")
        except ChallengeRequired as e:
            self.logger.warning(f"Challenge required for {self.username}: {str(e)}")
            return self._handle_challenge()
        except FeedbackRequired as e:
            self.logger.error(f"Account action blocked for {self.username}: {str(e)}")
        except PleaseWaitFewMinutes as e:
            self.logger.warning(f"Rate limit reached for {self.username}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected login error for {self.username}: {str(e)}")
        return False
    
    def _save_session(self):
        """Save current session data"""
        try:
            session_data = self.client.get_settings()
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            self.logger.info(f"Session saved for {self.username}")
        except Exception as e:
            self.logger.error(f"Failed to save session for {self.username}: {str(e)}")
    
    def _handle_challenge(self) -> bool:
        """Handle Instagram security challenges"""
        try:
            # Attempt automatic challenge resolution
            self.client.challenge_resolve(self.client.last_json)
            self._save_session()
            self.logger.info(f"Challenge resolved successfully for {self.username}")
            return True
        except Exception as e:
            self.logger.error(f"Challenge resolution failed for {self.username}: {str(e)}")
            return False
    
    def get_client(self) -> Optional[Client]:
        """Get authenticated Instagram client"""
        if self.authenticate():
            return self.client
        return None