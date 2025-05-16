from django.conf import settings
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

def generate_verification_token(user_id: str) -> str:
    """Generate a JWT token for email verification.
    
    Args:
        user_id: UUID of the user to verify.
        
    Returns:
        str: JWT token for email verification.
    """
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow() + timedelta(seconds=settings.VERIFICATION_TOKEN_TIMEOUT),
        'type': 'email_verification'
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def generate_password_reset_token(user_id: str) -> str:
    """Generate a JWT token for password reset.
    
    Args:
        user_id: UUID of the user resetting password.
        
    Returns:
        str: JWT token for password reset.
    """
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT),
        'type': 'password_reset'
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def verify_token(token: str, token_type: str) -> Optional[str]:
    """Verify a JWT token and return user ID if valid.
    
    Args:
        token: JWT token to verify.
        token_type: Type of token ('email_verification' or 'password_reset').
        
    Returns:
        Optional[str]: User ID if token is valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        if payload['type'] != token_type:
            return None
        return payload['user_id']
    except jwt.InvalidTokenError:
        return None

def send_verification_email(user_email: str, token: str) -> bool:
    """Send email verification link.
    
    Args:
        user_email: Email address to send to.
        token: Verification token.
        
    Returns:
        bool: True if email sent successfully.
    """
    verification_url = f"{settings.EMAIL_VERIFICATION_URL}?token={token}"
    
    context = {
        'verification_url': verification_url,
        'expiry_hours': settings.VERIFICATION_TOKEN_TIMEOUT // 3600
    }
    
    html_message = render_to_string('accounts/email/verify_email.html', context)
    plain_message = render_to_string('accounts/email/verify_email.txt', context)
    
    try:
        send_mail(
            subject=_('Verify your AbiaHub email address'),
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message
        )
        return True
    except Exception as e:
        print(f"Failed to send verification email: {str(e)}")
        return False

def send_password_reset_email(user_email: str, token: str) -> bool:
    """Send password reset link.
    
    Args:
        user_email: Email address to send to.
        token: Password reset token.
        
    Returns:
        bool: True if email sent successfully.
    """
    reset_url = f"{settings.PASSWORD_RESET_URL}?token={token}"
    
    context = {
        'reset_url': reset_url,
        'expiry_hours': settings.PASSWORD_RESET_TIMEOUT // 3600
    }
    
    html_message = render_to_string('accounts/email/reset_password.html', context)
    plain_message = render_to_string('accounts/email/reset_password.txt', context)
    
    try:
        send_mail(
            subject=_('Reset your AbiaHub password'),
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message
        )
        return True
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
        return False

def generate_temporary_password() -> str:
    """Generate a secure temporary password.
    
    Returns:
        str: Random password meeting security requirements.
    """
    return get_random_string(
        length=12,
        allowed_chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    ) 