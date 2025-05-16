"""Messaging services for SMS, WhatsApp, and notifications."""

import logging
from typing import Optional, Dict, Any
import requests
from django.conf import settings
from africastalking.SMS import SMS
from africastalking.USSD import USSD
from firebase_admin import messaging
from .base import BaseService

logger = logging.getLogger(__name__)

class MessagingService(BaseService):
    """Handles all messaging operations including SMS, WhatsApp, and push notifications."""
    
    def __init__(self):
        super().__init__()
        # Initialize Africa's Talking
        self.sms = SMS(
            username=settings.AT_USERNAME,
            api_key=settings.AT_API_KEY
        )
        self.ussd = USSD(
            username=settings.AT_USERNAME,
            api_key=settings.AT_API_KEY
        )
        
    async def send_sms(
        self,
        phone: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS using Africa's Talking.
        
        Args:
            phone: Recipient phone number (format: +2348012345678)
            message: Message content
            sender_id: Optional sender ID
            
        Returns:
            Dict containing status and message ID
        """
        try:
            response = await self.sms.send(
                message=message,
                recipients=[phone],
                sender_id=sender_id or settings.AT_SHORTCODE
            )
            
            logger.info(f"SMS sent to {phone}: {response}")
            return {
                'status': 'success',
                'message_id': response['SMSMessageData']['Recipients'][0]['messageId']
            }
            
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    async def send_whatsapp(
        self,
        phone: str,
        message: str,
        template_name: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send WhatsApp message using AiSensy API.
        
        Args:
            phone: Recipient phone number (format: 2348012345678)
            message: Message content or template name
            template_name: Optional template name for structured messages
            template_data: Optional template variables
            
        Returns:
            Dict containing status and message ID
        """
        try:
            url = "https://api.aisensy.com/v1/messages"
            headers = {
                "Authorization": f"Bearer {settings.AISENSY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "phone": phone,
                "instance_id": settings.AISENSY_INSTANCE_ID
            }
            
            if template_name:
                data.update({
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {
                            "code": "en"
                        },
                        "components": [
                            {
                                "type": "body",
                                "parameters": template_data
                            }
                        ]
                    }
                })
            else:
                data.update({
                    "type": "text",
                    "message": message
                })
                
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            logger.info(f"WhatsApp message sent to {phone}: {response.json()}")
            return {
                'status': 'success',
                'message_id': response.json()['message_id']
            }
            
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    async def send_push_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send push notification using Firebase Cloud Messaging.
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Optional data payload
            
        Returns:
            Dict containing status and message ID
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=token
            )
            
            response = messaging.send(message)
            logger.info(f"Push notification sent: {response}")
            
            return {
                'status': 'success',
                'message_id': response
            }
            
        except Exception as e:
            logger.error(f"Push notification failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    async def handle_ussd_session(
        self,
        phone: str,
        session_id: str,
        text: str
    ) -> Dict[str, Any]:
        """Handle USSD session using Africa's Talking.
        
        Args:
            phone: User's phone number
            session_id: USSD session ID
            text: User's input text
            
        Returns:
            Dict containing response message and action
        """
        try:
            # Initialize session if text is *384*1#
            if text == "*384*1#":
                return {
                    'message': (
                        "Welcome to AbiaHub\n"
                        "1. Report Issue\n"
                        "2. Check Status\n"
                        "3. View Services\n"
                        "4. Exit"
                    ),
                    'action': 'continue'
                }
                
            # Handle menu options
            parts = text.split('*')
            last_input = parts[-1]
            
            if len(parts) == 2:
                if last_input == "1":
                    return {
                        'message': (
                            "Select issue type:\n"
                            "1. Infrastructure\n"
                            "2. Security\n"
                            "3. Services\n"
                            "4. Other"
                        ),
                        'action': 'continue'
                    }
                elif last_input == "2":
                    # Fetch and return status
                    return {
                        'message': "No pending reports found",
                        'action': 'end'
                    }
                elif last_input == "3":
                    return {
                        'message': (
                            "Available services:\n"
                            "1. Business Registration\n"
                            "2. Tax Payment\n"
                            "3. License Renewal"
                        ),
                        'action': 'continue'
                    }
                elif last_input == "4":
                    return {
                        'message': "Thank you for using AbiaHub",
                        'action': 'end'
                    }
                    
            return {
                'message': "Invalid option selected",
                'action': 'end'
            }
            
        except Exception as e:
            logger.error(f"USSD session handling failed: {str(e)}")
            return {
                'message': "Service temporarily unavailable",
                'action': 'end'
            } 