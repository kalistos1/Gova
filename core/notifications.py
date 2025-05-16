"""Notification services for core app.

This module provides notification services for rewards and other core functionality.
"""

import logging
import requests
from typing import List, Optional, Tuple
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from .models import Reward

logger = logging.getLogger(__name__)

class RewardNotificationService:
    """Service for sending notifications about rewards.
    
    This service handles sending notifications to:
    - Users about their rewards (email and SMS)
    - Admins about failed rewards (email)
    - Users about failed rewards (email and SMS)
    """
    
    def __init__(self):
        """Initialize the notification service."""
        self.admin_email = settings.ADMIN_EMAIL
        self.from_email = settings.DEFAULT_FROM_EMAIL
        self.api_key = settings.AFRICAS_TALKING_API_KEY
        self.username = settings.AFRICAS_TALKING_USERNAME
        self.sms_url = 'https://api.africastalking.com/version1/messaging'
        
    def send_sms(self, phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """Send SMS via Africa's Talking API.
        
        Args:
            phone (str): Recipient's phone number
            message (str): Message to send
            
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            headers = {
                'apiKey': self.api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            data = {
                'username': self.username,
                'to': phone,
                'message': message,
                'from': 'ABIAHUB'  # Optional sender ID
            }
            
            response = requests.post(
                self.sms_url,
                headers=headers,
                data=data
            )
            
            if response.status_code == 201:
                result = response.json()
                if result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('status') == 'Success':
                    return True, None
                else:
                    error = result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('status')
                    return False, error
            else:
                return False, f'API error: {response.status_code}'
                
        except requests.RequestException as e:
            return False, f'Network error: {str(e)}'
        except Exception as e:
            logger.error(f'Unexpected error sending SMS: {str(e)}')
            return False, f'Unexpected error: {str(e)}'
    
    def send_reward_processed_notification(self, reward: Reward) -> bool:
        """Send notification when a reward is processed.
        
        Args:
            reward: The processed reward
            
        Returns:
            bool: True if all notifications were sent successfully
        """
        success = True
        
        # Send email notification
        if reward.user.email:
            try:
                context = {
                    'user': reward.user,
                    'reward': reward,
                    'amount': reward.amount,
                    'action_type': reward.get_action_type_display(),
                    'processed_at': reward.processed_at
                }
                
                subject = render_to_string(
                    'core/notifications/reward_processed_subject.txt',
                    context
                ).strip()
                
                html_message = render_to_string(
                    'core/notifications/reward_processed.html',
                    context
                )
                
                text_message = render_to_string(
                    'core/notifications/reward_processed.txt',
                    context
                )
                
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=self.from_email,
                    recipient_list=[reward.user.email],
                    html_message=html_message
                )
                
                logger.info(
                    f'Sent reward processed email to {reward.user.email} '
                    f'for reward {reward.id}'
                )
                
            except Exception as e:
                logger.error(
                    f'Failed to send reward processed email: {str(e)}'
                )
                success = False
        
        # Send SMS notification
        if reward.user.phone_number:
            try:
                message = (
                    f'Your {reward.get_action_type_display()} reward of '
                    f'{reward.amount} NGN has been processed. '
                    f'Thank you for your contribution to AbiaHub!'
                )
                
                sms_success, error = self.send_sms(
                    reward.user.phone_number,
                    message
                )
                
                if sms_success:
                    logger.info(
                        f'Sent reward processed SMS to {reward.user.phone_number} '
                        f'for reward {reward.id}'
                    )
                else:
                    logger.error(
                        f'Failed to send reward processed SMS: {error}'
                    )
                    success = False
                    
            except Exception as e:
                logger.error(
                    f'Failed to send reward processed SMS: {str(e)}'
                )
                success = False
        
        return success
    
    def send_reward_failed_notification(
        self,
        reward: Reward,
        notify_admin: bool = True
    ) -> bool:
        """Send notification when a reward fails.
        
        Args:
            reward: The failed reward
            notify_admin: Whether to notify admin (default: True)
            
        Returns:
            bool: True if all notifications were sent successfully
        """
        success = True
        
        # Send email notification to user
        if reward.user.email:
            try:
                context = {
                    'user': reward.user,
                    'reward': reward,
                    'amount': reward.amount,
                    'action_type': reward.get_action_type_display(),
                    'failure_reason': reward.failure_reason
                }
                
                subject = render_to_string(
                    'core/notifications/reward_failed_subject.txt',
                    context
                ).strip()
                
                html_message = render_to_string(
                    'core/notifications/reward_failed.html',
                    context
                )
                
                text_message = render_to_string(
                    'core/notifications/reward_failed.txt',
                    context
                )
                
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=self.from_email,
                    recipient_list=[reward.user.email],
                    html_message=html_message
                )
                
                logger.info(
                    f'Sent reward failed email to {reward.user.email} '
                    f'for reward {reward.id}'
                )
                
            except Exception as e:
                logger.error(
                    f'Failed to send reward failed email to user: {str(e)}'
                )
                success = False
        
        # Send SMS notification to user
        if reward.user.phone_number:
            try:
                message = (
                    f'Your {reward.get_action_type_display()} reward of '
                    f'{reward.amount} NGN could not be processed. '
                    f'Reason: {reward.failure_reason}. '
                    f'Please verify your phone number in your profile settings.'
                )
                
                sms_success, error = self.send_sms(
                    reward.user.phone_number,
                    message
                )
                
                if sms_success:
                    logger.info(
                        f'Sent reward failed SMS to {reward.user.phone_number} '
                        f'for reward {reward.id}'
                    )
                else:
                    logger.error(
                        f'Failed to send reward failed SMS: {error}'
                    )
                    success = False
                    
            except Exception as e:
                logger.error(
                    f'Failed to send reward failed SMS: {str(e)}'
                )
                success = False
        
        # Send email notification to admin
        if notify_admin:
            try:
                context = {
                    'reward': reward,
                    'user': reward.user,
                    'amount': reward.amount,
                    'action_type': reward.get_action_type_display(),
                    'failure_reason': reward.failure_reason,
                    'admin_url': f'{settings.FRONTEND_URL}/admin/core/reward/{reward.id}/change/'
                }
                
                subject = render_to_string(
                    'core/notifications/reward_failed_admin_subject.txt',
                    context
                ).strip()
                
                html_message = render_to_string(
                    'core/notifications/reward_failed_admin.html',
                    context
                )
                
                text_message = render_to_string(
                    'core/notifications/reward_failed_admin.txt',
                    context
                )
                
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=self.from_email,
                    recipient_list=[self.admin_email],
                    html_message=html_message
                )
                
                logger.info(
                    f'Sent reward failed notification to admin for reward {reward.id}'
                )
                
            except Exception as e:
                logger.error(
                    f'Failed to send reward failed notification to admin: {str(e)}'
                )
                success = False
        
        return success
    
    def send_bulk_failure_report(
        self,
        failed_rewards: List[Reward],
        batch_id: Optional[str] = None
    ) -> bool:
        """Send a report about multiple failed rewards.
        
        Args:
            failed_rewards: List of failed rewards
            batch_id: Optional batch identifier
            
        Returns:
            bool: True if notification was sent successfully
        """
        if not failed_rewards:
            return True
            
        try:
            context = {
                'failed_rewards': failed_rewards,
                'count': len(failed_rewards),
                'batch_id': batch_id or timezone.now().strftime('%Y%m%d_%H%M%S'),
                'admin_url': f'{settings.FRONTEND_URL}/admin/core/reward/'
            }
            
            subject = render_to_string(
                'core/notifications/bulk_failure_report_subject.txt',
                context
            ).strip()
            
            html_message = render_to_string(
                'core/notifications/bulk_failure_report.html',
                context
            )
            
            text_message = render_to_string(
                'core/notifications/bulk_failure_report.txt',
                context
            )
            
            send_mail(
                subject=subject,
                message=text_message,
                from_email=self.from_email,
                recipient_list=[self.admin_email],
                html_message=html_message
            )
            
            logger.info(
                f'Sent bulk failure report for {len(failed_rewards)} rewards '
                f'(batch: {context["batch_id"]})'
            )
            return True
            
        except Exception as e:
            logger.error(f'Failed to send bulk failure report: {str(e)}')
            return False 