"""Utility functions for core app.

This module provides utility functions for various operations including:
- Image metadata extraction
- Report prioritization using AI
- Voice transcription
- NIN verification
- Payment processing
- USSD/SMS messaging
- Blockchain transaction recording
- File validation and processing
- Data sanitization
- Rate limiting and caching
- Notification handling
- Analytics tracking

All functions use environment variables for API keys and endpoints,
and include proper error handling and logging.
"""

import json
import logging
import hashlib
import time
from typing import Dict, Any, Optional, Tuple, Union, List, Callable
from decimal import Decimal
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
import mimetypes
import re
import os

import requests
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from decouple import config
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

# Custom Exceptions
class APIError(Exception):
    """Base exception for API-related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)

class ValidationAPIError(APIError):
    """Raised when API validation fails."""
    pass

class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    pass

class RetryableAPIError(APIError):
    """Raised when API request should be retried."""
    pass

class BlockchainError(APIError):
    """Raised when blockchain-related errors occur."""
    pass

# Rate Limiting Decorator
def rate_limit(limit: int, period: int = 60):
    """Rate limiting decorator for API calls.
    
    Args:
        limit: Maximum number of calls allowed in the period
        period: Time period in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f'rate_limit:{func.__name__}:{hash(str(args) + str(kwargs))}'
            current = cache.get(key, 0)
            
            if current >= limit:
                raise RateLimitError(
                    f'Rate limit exceeded. Maximum {limit} calls per {period} seconds.'
                )
            
            cache.set(key, current + 1, period)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# File Validation Functions
def validate_file(
    file: UploadedFile,
    allowed_types: List[str],
    max_size_mb: int = 5
) -> None:
    """Validate uploaded file type and size.
    
    Args:
        file: Uploaded file object
        allowed_types: List of allowed MIME types
        max_size_mb: Maximum file size in MB
        
    Raises:
        ValidationError: If file is invalid
    """
    if not file:
        raise ValidationError(_('No file provided'))
        
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        raise ValidationError(
            _('File size exceeds maximum allowed size of %(size)s MB'),
            params={'size': max_size_mb}
        )
    
    # Check file type
    mime_type, _ = mimetypes.guess_type(file.name)
    if not mime_type or mime_type not in allowed_types:
        raise ValidationError(
            _('Invalid file type. Allowed types: %(types)s'),
            params={'types': ', '.join(allowed_types)}
        )

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent security issues.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = Path(filename).name
    
    # Replace invalid characters
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    
    # Ensure unique filename
    timestamp = int(time.time())
    name, ext = os.path.splitext(filename)
    return f"{name}_{timestamp}{ext}"

# Data Validation Functions
def validate_phone_number(phone: str) -> str:
    """Validate and format phone number.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Formatted phone number
        
    Raises:
        ValidationError: If phone number is invalid
    """
    # Remove any non-digit characters
    phone = re.sub(r'\D', '', phone)
    
    # Validate Nigerian phone number format
    if not re.match(r'^(\+234|0)[789][01]\d{8}$', phone):
        raise ValidationError(_('Invalid phone number format'))
    
    # Convert to international format
    if phone.startswith('0'):
        phone = '+234' + phone[1:]
    elif not phone.startswith('+234'):
        phone = '+234' + phone
        
    return phone

def validate_email(email: str) -> str:
    """Validate and sanitize email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        Sanitized email address
        
    Raises:
        ValidationError: If email is invalid
    """
    email = email.strip().lower()
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError(_('Invalid email address format'))
        
    return email

# Enhanced API Request Function
def _make_api_request(
    url: str,
    method: str = 'POST',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: int = 1
) -> Dict[str, Any]:
    """Make an API request with retry mechanism and enhanced error handling.
    
    Args:
        url: The API endpoint URL
        method: HTTP method (default: POST)
        headers: Request headers
        data: Request payload
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Dict containing the API response
        
    Raises:
        APIError: If the API request fails after retries
        ValidationAPIError: If the request data is invalid
        RateLimitError: If rate limit is exceeded
        RetryableAPIError: If request should be retried
    """
    headers = headers or {}
    data = data or {}
    
    for attempt in range(max_retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', retry_delay))
                raise RateLimitError(
                    'Rate limit exceeded',
                    status_code=429,
                    response=response.json()
                )
            
            # Handle validation errors
            if response.status_code == 400:
                raise ValidationAPIError(
                    'Invalid request data',
                    status_code=400,
                    response=response.json()
                )
            
            # Handle server errors
            if response.status_code >= 500:
                raise RetryableAPIError(
                    'Server error occurred',
                    status_code=response.status_code,
                    response=response.json()
                )
            
            response.raise_for_status()
            return response.json()
            
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == max_retries - 1:
                raise RetryableAPIError(f'Request failed after {max_retries} attempts: {str(e)}')
            time.sleep(retry_delay * (attempt + 1))
            
        except requests.RequestException as e:
            logger.error(
                'API request failed',
                extra={
                    'url': url,
                    'method': method,
                    'status_code': getattr(e.response, 'status_code', None),
                    'response': getattr(e.response, 'text', None),
                    'attempt': attempt + 1
                }
            )
            raise APIError(str(e), getattr(e.response, 'status_code', None))
            
    raise RetryableAPIError(f'Request failed after {max_retries} attempts')

# Notification Functions
def send_notification(
    user_id: int,
    title: str,
    message: str,
    notification_type: str = 'info',
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Send notification to user through multiple channels.
    
    Args:
        user_id: ID of the user to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification (info/warning/error)
        data: Additional notification data
        
    Returns:
        Dict containing notification status
    """
    try:
        # Store notification in database
        notification = {
            'user_id': user_id,
            'title': title,
            'message': message,
            'type': notification_type,
            'data': data or {},
            'created_at': datetime.now().isoformat()
        }
        
        # TODO: Store notification in database
        
        # Send push notification if user has device tokens
        # TODO: Implement push notification sending
        
        # Send email notification
        # TODO: Implement email sending
        
        return {
            'status': 'sent',
            'notification_id': notification.get('id'),
            'channels': ['database', 'push', 'email'],
            'created_at': notification['created_at']
        }
        
    except Exception as e:
        logger.error(f'Failed to send notification: {str(e)}')
        raise APIError('Failed to send notification')

# Analytics Functions
def track_event(
    event_name: str,
    user_id: Optional[int] = None,
    properties: Optional[Dict[str, Any]] = None
) -> None:
    """Track user event for analytics.
    
    Args:
        event_name: Name of the event
        user_id: ID of the user performing the event
        properties: Additional event properties
    """
    try:
        event = {
            'event': event_name,
            'user_id': user_id,
            'properties': properties or {},
            'timestamp': datetime.now().isoformat(),
            'session_id': cache.get(f'user_session:{user_id}') if user_id else None
        }
        
        # TODO: Send event to analytics service
        
        logger.info(
            'Event tracked',
            extra={
                'event_name': event_name,
                'user_id': user_id,
                'properties': properties
            }
        )
        
    except Exception as e:
        logger.error(f'Failed to track event: {str(e)}')
        # Don't raise exception to prevent disrupting user flow

def extract_exif_geolocation(image_file) -> Optional[Dict[str, float]]:
    """Extract GPS coordinates from image EXIF metadata.
    
    Args:
        image_file: File object or path to the image
        
    Returns:
        Dict containing latitude and longitude, or None if not found
        
    Raises:
        ValidationError: If the image is invalid or corrupted
    """
    try:
        with Image.open(image_file) as img:
            if not hasattr(img, '_getexif') or img._getexif() is None:
                return None
                
            exif = {
                TAGS[k]: v
                for k, v in img._getexif().items()
                if k in TAGS
            }
            
            if 'GPSInfo' not in exif:
                return None
                
            gps_info = {
                GPSTAGS[k]: v
                for k, v in exif['GPSInfo'].items()
                if k in GPSTAGS
            }
            
            if not all(k in gps_info for k in ['GPSLatitude', 'GPSLongitude']):
                return None
                
            lat = gps_info['GPSLatitude']
            lon = gps_info['GPSLongitude']
            
            # Convert to decimal degrees
            lat = lat[0] + lat[1]/60 + lat[2]/3600
            lon = lon[0] + lon[1]/60 + lon[2]/3600
            
            if gps_info.get('GPSLatitudeRef') == 'S':
                lat = -lat
            if gps_info.get('GPSLongitudeRef') == 'W':
                lon = -lon
                
            return {
                'latitude': round(lat, 6),
                'longitude': round(lon, 6)
            }
    except Exception as e:
        logger.error(f'Failed to extract EXIF data: {str(e)}')
        raise ValidationError(_('Invalid or corrupted image file'))


def prioritize_report(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prioritize report urgency using OpenRouter AI.
    
    Args:
        report_data: Dict containing report details
        
    Returns:
        Dict containing priority score and analysis
        
    Raises:
        requests.RequestException: If the API request fails
    """
    api_key = config('OPENROUTER_API_KEY')
    url = 'https://openrouter.ai/api/v1/prioritize'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = _make_api_request(
            url=url,
            headers=headers,
            data=report_data
        )
        
        return {
            'priorityScore': response.get('score', 0),
            'analysis': response.get('analysis', ''),
            'recommendedAction': response.get('action', ''),
            'confidence': response.get('confidence', 0)
        }
    except Exception as e:
        logger.error(f'Report prioritization failed: {str(e)}')
        raise


def transcribe_voice(
    audio_file: Any,
    language: str = 'en'
) -> Dict[str, Any]:
    """Transcribe voice to text using OpenRouter AI.
    
    Args:
        audio_file: File object or path to the audio file
        language: Language code (en/ig/pidgin)
        
    Returns:
        Dict containing transcription and metadata
        
    Raises:
        ValidationError: If the audio file is invalid
        requests.RequestException: If the API request fails
    """
    api_key = config('OPENROUTER_API_KEY')
    url = 'https://openrouter.ai/api/v1/transcribe'
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    files = {
        'audio': ('audio.wav', audio_file, 'audio/wav')
    }
    
    data = {
        'language': language,
        'model': 'whisper-large-v3'
    }
    
    try:
        response = requests.post(
            url=url,
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        return {
            'transcription': result.get('text', ''),
            'language': result.get('language', language),
            'confidence': result.get('confidence', 0),
            'duration': result.get('duration', 0)
        }
    except requests.RequestException as e:
        logger.error(f'Voice transcription failed: {str(e)}')
        raise
    except Exception as e:
        logger.error(f'Invalid audio file: {str(e)}')
        raise ValidationError(_('Invalid or corrupted audio file'))


def verify_nin(nin: str, phone: str) -> Dict[str, Any]:
    """Verify NIN using VerifyMe API.
    
    Args:
        nin: National Identity Number
        phone: Phone number associated with NIN
        
    Returns:
        Dict containing verification status and details
        
    Raises:
        ValidationError: If the NIN or phone is invalid
        requests.RequestException: If the API request fails
    """
    api_key = config('VERIFYME_API_KEY')
    url = 'https://vapi.verifyme.ng/v1/verifications/identities/nin'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'nin': nin,
        'phone': phone
    }
    
    try:
        response = _make_api_request(
            url=url,
            headers=headers,
            data=data
        )
        
        return {
            'isVerified': response.get('verified', False),
            'fullName': response.get('full_name', ''),
            'dateOfBirth': response.get('dob', ''),
            'gender': response.get('gender', ''),
            'photoUrl': response.get('photo_url', ''),
            'verificationDate': datetime.now().isoformat()
        }
    except requests.RequestException as e:
        logger.error(f'NIN verification failed: {str(e)}')
        raise
    except Exception as e:
        logger.error(f'Invalid NIN data: {str(e)}')
        raise ValidationError(_('Invalid NIN or phone number'))


def process_payment(
    amount: Decimal,
    user: Any,
    description: str
) -> Dict[str, Any]:
    """Process payment using Flutterwave API.
    
    Args:
        amount: Payment amount in NGN
        user: User object making the payment
        description: Payment description
        
    Returns:
        Dict containing payment status and details
        
    Raises:
        ValidationError: If the payment data is invalid
        requests.RequestException: If the API request fails
    """
    api_key = config('FLUTTERWAVE_SECRET_KEY')
    url = 'https://api.flutterwave.com/v3/payments'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'tx_ref': f'ABIA-{datetime.now().timestamp()}',
        'amount': str(amount),
        'currency': 'NGN',
        'payment_options': 'card,ussd',
        'customer': {
            'email': user.email,
            'name': user.get_full_name(),
            'phone_number': user.phone_number
        },
        'customizations': {
            'title': 'AbiaHub Payment',
            'description': description,
            'logo': settings.SITE_LOGO_URL
        },
        'meta': {
            'user_id': user.id,
            'payment_type': 'grant_application'
        }
    }
    
    try:
        response = _make_api_request(
            url=url,
            headers=headers,
            data=data
        )
        
        return {
            'paymentId': response.get('id'),
            'reference': response.get('tx_ref'),
            'amount': amount,
            'status': response.get('status'),
            'paymentUrl': response.get('link'),
            'expiresAt': response.get('expires_at')
        }
    except requests.RequestException as e:
        logger.error(f'Payment processing failed: {str(e)}')
        raise
    except Exception as e:
        logger.error(f'Invalid payment data: {str(e)}')
        raise ValidationError(_('Invalid payment details'))


def send_ussd_sms(
    message: str,
    phone: str,
    is_ussd: bool = False
) -> Dict[str, Any]:
    """Send USSD prompt or SMS using Africa's Talking API.
    
    Args:
        message: Message content
        phone: Recipient phone number
        is_ussd: Whether to send as USSD prompt
        
    Returns:
        Dict containing message status and details
        
    Raises:
        ValidationError: If the message data is invalid
        requests.RequestException: If the API request fails
    """
    api_key = config('AFRICASTALKING_API_KEY')
    username = config('AFRICASTALKING_USERNAME')
    
    if is_ussd:
        url = 'https://api.africastalking.com/version1/ussd'
        data = {
            'username': username,
            'message': message,
            'phoneNumber': phone
        }
    else:
        url = 'https://api.africastalking.com/version1/messaging'
        data = {
            'username': username,
            'message': message,
            'recipients': [phone]
        }
    
    headers = {
        'apiKey': api_key,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        response = requests.post(
            url=url,
            headers=headers,
            data=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        if is_ussd:
            return {
                'sessionId': result.get('sessionId'),
                'message': message,
                'phoneNumber': phone,
                'status': 'sent'
            }
        else:
            return {
                'messageId': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('messageId'),
                'message': message,
                'recipient': phone,
                'status': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('status'),
                'cost': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('cost')
            }
    except requests.RequestException as e:
        logger.error(f'Message sending failed: {str(e)}')
        raise
    except Exception as e:
        logger.error(f'Invalid message data: {str(e)}')
        raise ValidationError(_('Invalid message or phone number'))


def record_blockchain_transaction(
    application_id: int,
    amount: Decimal,
    description: str
) -> Dict[str, Any]:
    """Record grant transaction on Stellar blockchain.
    
    Args:
        application_id: ID of the grant application
        amount: Grant amount in NGN
        description: Transaction description
        
    Returns:
        Dict containing transaction status and details
        
    Raises:
        ValidationError: If the transaction data is invalid
        BlockchainError: If the blockchain transaction fails
        APIError: If the API request fails
    """
    try:
        # Validate input
        if not application_id:
            raise ValidationError(_('Application ID is required'))
        if not amount or amount <= 0:
            raise ValidationError(_('Amount must be greater than 0'))
        if not description:
            raise ValidationError(_('Description is required'))
            
        # Get API credentials
        api_key = config('STELLAR_API_KEY')
        if not api_key:
            raise ValidationError(_('Stellar API key not configured'))
            
        source_account = config('STELLAR_SOURCE_ACCOUNT')
        if not source_account:
            raise ValidationError(_('Stellar source account not configured'))
            
        destination_account = config('STELLAR_DESTINATION_ACCOUNT')
        if not destination_account:
            raise ValidationError(_('Stellar destination account not configured'))
            
        # Prepare request
        url = 'https://horizon.stellar.org/transactions'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'application_id': application_id,
            'amount': str(amount),
            'currency': 'NGN',
            'description': description,
            'memo': f'GRANT-{application_id}',
            'memo_type': 'text',
            'source_account': source_account,
            'destination_account': destination_account
        }
        
        # Make API request with retry
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = _make_api_request(
                    url=url,
                    headers=headers,
                    data=data,
                    timeout=30
                )
                
                # Validate response
                if not response:
                    raise APIError(_('Empty response from Stellar API'))
                    
                transaction_id = response.get('id')
                if not transaction_id:
                    raise APIError(_('Missing transaction ID in response'))
                    
                transaction_hash = response.get('hash')
                if not transaction_hash:
                    raise APIError(_('Missing transaction hash in response'))
                    
                # Return transaction details
                return {
                    'transactionId': transaction_id,
                    'applicationId': application_id,
                    'amount': amount,
                    'status': response.get('status', 'pending'),
                    'hash': transaction_hash,
                    'ledger': response.get('ledger'),
                    'createdAt': response.get('created_at'),
                    'memo': description
                }
                
            except requests.Timeout:
                logger.warning(
                    'Blockchain transaction timeout',
                    extra={
                        'attempt': attempt + 1,
                        'application_id': application_id,
                        'amount': str(amount)
                    }
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise BlockchainError(_('Transaction timed out'))
                
            except requests.RequestException as e:
                logger.error(
                    'Blockchain API request failed',
                    extra={
                        'error': str(e),
                        'attempt': attempt + 1,
                        'application_id': application_id,
                        'amount': str(amount)
                    }
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise BlockchainError(_('Failed to connect to blockchain'))
                
            except Exception as e:
                logger.error(
                    'Unexpected blockchain error',
                    extra={
                        'error': str(e),
                        'application_id': application_id,
                        'amount': str(amount)
                    },
                    exc_info=True
                )
                raise BlockchainError(_('Unexpected blockchain error'))
                
    except ValidationError:
        raise
    except (BlockchainError, APIError):
        raise
    except Exception as e:
        logger.error(
            'Failed to record blockchain transaction',
            extra={
                'error': str(e),
                'application_id': application_id,
                'amount': str(amount)
            },
            exc_info=True
        )
        raise BlockchainError(_('Failed to record transaction')) 