"""Services for core app functionality.

This module provides service classes for processing rewards and other core functionality.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Reward
from .notifications import RewardNotificationService

logger = logging.getLogger(__name__)

class RewardProcessor:
    """Service class for processing pending rewards.
    
    This class handles the processing of pending rewards through the Africa's Talking API,
    including retry logic, error handling, and status updates.
    
    Attributes:
        api_key (str): Africa's Talking API key
        username (str): Africa's Talking username
        base_url (str): Africa's Talking API base URL
        max_retries (int): Maximum number of retry attempts
        batch_size (int): Number of rewards to process in one batch
    """
    
    def __init__(self):
        """Initialize the reward processor with API credentials."""
        self.api_key = settings.AFRICAS_TALKING_API_KEY
        self.username = settings.AFRICAS_TALKING_USERNAME
        self.base_url = 'https://api.africastalking.com/version1/airtime/send'
        self.max_retries = settings.REWARD_PROCESSING_MAX_RETRIES
        self.batch_size = settings.REWARD_PROCESSING_BATCH_SIZE
        self.notification_service = RewardNotificationService()
        
    def get_pending_rewards(self) -> List[Reward]:
        """Get a batch of pending rewards to process.
        
        Returns:
            List[Reward]: List of pending rewards, ordered by creation date
        """
        return Reward.objects.filter(
            status='PENDING'
        ).order_by('created_at')[:self.batch_size]
    
    def format_phone_number(self, phone: str) -> str:
        """Format phone number for Africa's Talking API.
        
        Args:
            phone (str): Raw phone number
            
        Returns:
            str: Formatted phone number (e.g., +2348012345678)
            
        Raises:
            ValueError: If phone number is invalid
        """
        # Remove any non-digit characters
        digits = ''.join(filter(str.isdigit, phone))
        
        # Handle Nigerian numbers
        if len(digits) == 11 and digits.startswith('0'):
            return f'+234{digits[1:]}'
        elif len(digits) == 13 and digits.startswith('234'):
            return f'+{digits}'
        else:
            raise ValueError(f'Invalid phone number format: {phone}')
    
    def send_airtime(self, phone: str, amount: Decimal) -> Tuple[bool, Optional[str]]:
        """Send airtime via Africa's Talking API.
        
        Args:
            phone (str): Recipient's phone number
            amount (Decimal): Amount of airtime in NGN
            
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            formatted_phone = self.format_phone_number(phone)
            
            headers = {
                'apiKey': self.api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            data = {
                'username': self.username,
                'recipients': [{
                    'phoneNumber': formatted_phone,
                    'amount': f'NGN {amount}'
                }]
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data
            )
            
            if response.status_code == 201:
                result = response.json()
                if result.get('responses', [{}])[0].get('status') == 'Success':
                    return True, None
                else:
                    error = result.get('responses', [{}])[0].get('errorMessage', 'Unknown error')
                    return False, error
            else:
                return False, f'API error: {response.status_code}'
                
        except requests.RequestException as e:
            return False, f'Network error: {str(e)}'
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f'Unexpected error sending airtime: {str(e)}')
            return False, f'Unexpected error: {str(e)}'
    
    @transaction.atomic
    def process_reward(self, reward: Reward) -> bool:
        """Process a single reward.
        
        Args:
            reward (Reward): The reward to process
            
        Returns:
            bool: True if processing was successful
        """
        if reward.status != 'PENDING':
            logger.warning(f'Reward {reward.id} is not pending (status: {reward.status})')
            return False
            
        if not reward.user.phone_number:
            reward.status = 'FAILED'
            reward.failure_reason = 'User has no phone number'
            reward.save()
            
            # Notify about missing phone number
            self.notification_service.send_reward_failed_notification(reward)
            return False
            
        # Try to send airtime with retries
        for attempt in range(self.max_retries):
            success, error = self.send_airtime(
                reward.user.phone_number,
                reward.amount
            )
            
            if success:
                reward.status = 'PROCESSED'
                reward.processed_at = timezone.now()
                reward.save()
                
                # Send success notification
                self.notification_service.send_reward_processed_notification(reward)
                
                logger.info(
                    f'Successfully processed reward {reward.id} '
                    f'({reward.amount} NGN to {reward.user})'
                )
                return True
                
            if attempt < self.max_retries - 1:
                logger.warning(
                    f'Attempt {attempt + 1} failed for reward {reward.id}: {error}. '
                    'Retrying...'
                )
                continue
                
        # All retries failed
        reward.status = 'FAILED'
        reward.failure_reason = error
        reward.save()
        
        # Send failure notification
        self.notification_service.send_reward_failed_notification(reward)
        
        logger.error(
            f'Failed to process reward {reward.id} after {self.max_retries} attempts: {error}'
        )
        return False
    
    def process_pending_rewards(self) -> Tuple[int, int, int]:
        """Process a batch of pending rewards.
        
        Returns:
            Tuple[int, int, int]: (processed_count, failed_count, skipped_count)
        """
        rewards = self.get_pending_rewards()
        processed = failed = skipped = 0
        failed_rewards = []
        
        for reward in rewards:
            try:
                if self.process_reward(reward):
                    processed += 1
                else:
                    failed += 1
                    if reward.status == 'FAILED':
                        failed_rewards.append(reward)
            except Exception as e:
                logger.error(f'Error processing reward {reward.id}: {str(e)}')
                skipped += 1
                
        # Send bulk failure report if there are failed rewards
        if failed_rewards:
            self.notification_service.send_bulk_failure_report(failed_rewards)
                
        logger.info(
            f'Reward processing batch complete: '
            f'{processed} processed, {failed} failed, {skipped} skipped'
        )
        
        return processed, failed, skipped 