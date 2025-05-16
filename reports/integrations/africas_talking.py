"""Africa's Talking integration for USSD and SMS functionality."""

import africastalking
from django.conf import settings
from typing import Dict, List, Optional
import logging
from django.utils.translation import gettext as _
import asyncio
from typing import Any

logger = logging.getLogger(__name__)



class AfricasTalkingClient:
    """Client for Africa's Talking USSD and SMS services."""

    def __init__(self):
        """Initialize the Africa's Talking client."""
        self.username = settings.AT_USERNAME
        self.api_key = settings.AT_API_KEY
        
        # Initialize Africa's Talking
        africastalking.initialize(self.username, self.api_key)
        self.sms = africastalking.SMS
        self.ussd = africastalking.USSD
        
        # USSD menu states
        self.STATES = {
            'MAIN_MENU': 1,
            'REPORT_CATEGORY': 2,
            'REPORT_DESCRIPTION': 3,
            'REPORT_LOCATION': 4,
            'REPORT_CONFIRM': 5
        }


    async def send_sms(
        self,
        to: str | List[str],
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS message(s).
        
        Args:
            to: Phone number(s) to send to
            message: Message content
            sender_id: Optional sender ID
            
        Returns:
            Dict containing send result
            
        Raises:
            Exception: If SMS sending fails
        """
        try:
            # Ensure phone numbers are in international format
            if isinstance(to, str):
                recipients = [to]
            else:
                recipients = to
                
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sms.send(
                    message,
                    recipients,
                    sender_id=sender_id or settings.AT_SENDER_ID
                )
            )
            
            return {
                'status': 'success',
                'message_id': response['SMSMessageData']['Recipients'][0]['messageId'],
                'number_of_recipients': len(recipients),
                'cost': response['SMSMessageData']['Recipients'][0]['cost']
            }
            
        except Exception as e:
            logger.error(f'SMS sending failed: {str(e)}')
            return {
                'status': 'error',
                'message': str(e)
            }

    def handle_ussd(
        self,
        session_id: str,
        phone_number: str,
        text: str,
        network_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle USSD session.
        
        Args:
            session_id: USSD session ID
            phone_number: User's phone number
            text: USSD input text
            network_code: Optional network code
            
        Returns:
            Dict containing USSD response
        """
        try:
            # Get session state
            state = self._get_session_state(session_id)
            
            if not text:  # Initial request
                return self._main_menu()
                
            if state == self.STATES['MAIN_MENU']:
                return self._handle_main_menu(text)
                
            elif state == self.STATES['REPORT_CATEGORY']:
                return self._handle_category_selection(text)
                
            elif state == self.STATES['REPORT_DESCRIPTION']:
                return self._handle_description(text)
                
            elif state == self.STATES['REPORT_LOCATION']:
                return self._handle_location(text)
                
            elif state == self.STATES['REPORT_CONFIRM']:
                return self._handle_confirmation(text)
                
            else:
                return self._main_menu()
                
        except Exception as e:
            logger.error(f'USSD handling failed: {str(e)}')
            return {
                'status': 'error',
                'message': _('An error occurred. Please try again.')
            }

    def _main_menu(self) -> Dict[str, Any]:
        """Display main USSD menu."""
        menu = "Welcome to AbiaHub\n"
        menu += "1. Submit Report\n"
        menu += "2. Check Report Status\n"
        menu += "3. Emergency Numbers\n"
        menu += "4. Exit"
        
        return {
            'status': 'success',
            'message': menu,
            'state': self.STATES['MAIN_MENU']
        }

    def _handle_main_menu(self, text: str) -> Dict[str, Any]:
        """Handle main menu selection."""
        if text == '1':
            menu = "Select Report Category:\n"
            menu += "1. Infrastructure\n"
            menu += "2. Security\n"
            menu += "3. Healthcare\n"
            menu += "4. Education\n"
            menu += "5. Environment\n"
            menu += "0. Back"
            
            return {
                'status': 'success',
                'message': menu,
                'state': self.STATES['REPORT_CATEGORY']
            }
            
        elif text == '2':
            return {
                'status': 'success',
                'message': "Enter your Report ID:",
                'state': self.STATES['CHECK_STATUS']
            }
            
        elif text == '3':
            menu = "Emergency Numbers:\n"
            menu += "Police: 112\n"
            menu += "Fire: 112\n"
            menu += "Ambulance: 112\n"
            menu += "0. Back"
            
            return {
                'status': 'success',
                'message': menu,
                'state': self.STATES['MAIN_MENU']
            }
            
        elif text == '4':
            return {
                'status': 'success',
                'message': "Thank you for using AbiaHub",
                'state': 'END'
            }
            
        else:
            return self._main_menu()

    def _handle_category_selection(self, text: str) -> Dict[str, Any]:
        """Handle report category selection."""
        categories = {
            '1': 'INFRASTRUCTURE',
            '2': 'SECURITY',
            '3': 'HEALTH',
            '4': 'EDUCATION',
            '5': 'ENVIRONMENT'
        }
        
        if text == '0':
            return self._main_menu()
            
        if text in categories:
            return {
                'status': 'success',
                'message': "Enter report description:",
                'state': self.STATES['REPORT_DESCRIPTION'],
                'category': categories[text]
            }
            
        return {
            'status': 'error',
            'message': "Invalid selection. Try again.",
            'state': self.STATES['REPORT_CATEGORY']
        }

    def _handle_description(self, text: str) -> Dict[str, Any]:
        """Handle report description input."""
        if len(text.strip()) < 10:
            return {
                'status': 'error',
                'message': "Description too short. Please provide more details.",
                'state': self.STATES['REPORT_DESCRIPTION']
            }
            
        return {
            'status': 'success',
            'message': "Enter location (LGA, Area):",
            'state': self.STATES['REPORT_LOCATION'],
            'description': text
        }

    def _handle_location(self, text: str) -> Dict[str, Any]:
        """Handle location input."""
        if len(text.strip()) < 5:
            return {
                'status': 'error',
                'message': "Please provide more location details.",
                'state': self.STATES['REPORT_LOCATION']
            }
            
        summary = "Confirm Report Details:\n"
        summary += f"Category: {self._get_session_data('category')}\n"
        summary += f"Description: {self._get_session_data('description')}\n"
        summary += f"Location: {text}\n\n"
        summary += "1. Confirm\n"
        summary += "2. Cancel"
        
        return {
            'status': 'success',
            'message': summary,
            'state': self.STATES['REPORT_CONFIRM'],
            'location': text
        }

    def _handle_confirmation(self, text: str) -> Dict[str, Any]:
        """Handle report confirmation."""
        if text == '1':
            # Create report
            try:
                from reports.models import Report
                report = Report.objects.create(
                    category=self._get_session_data('category'),
                    description=self._get_session_data('description'),
                    address=self._get_session_data('location'),
                    submission_channel='USSD'
                )
                
                return {
                    'status': 'success',
                    'message': f"Report submitted successfully.\nReport ID: {report.id}",
                    'state': 'END'
                }
                
            except Exception as e:
                logger.error(f'Failed to create report via USSD: {str(e)}')
                return {
                    'status': 'error',
                    'message': "Failed to submit report. Please try again.",
                    'state': 'END'
                }
                
        else:
            return {
                'status': 'success',
                'message': "Report cancelled.",
                'state': 'END'
            }

    def _get_session_state(self, session_id: str) -> int:
        """Get current session state."""
        # In a real implementation, this would use Redis/cache
        return 1  # Default to main menu

    def _get_session_data(self, key: str) -> Optional[str]:
        """Get session data."""
        # In a real implementation, this would use Redis/cache
        return None 