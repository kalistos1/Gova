"""API views for authentication and user management.

This module provides views for:
- NIN verification and JWT token generation
- JWT token refresh
- User profile management
"""
from rest_framework.request import Request 
from rest_framework.views import APIView
import logging
import re
from typing import Dict, Any, Optional
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.utils import verify_nin, validate_phone_number
from core.models import AuditLog
from accounts.models import User
from accounts.serializers import UserSerializer

logger = logging.getLogger(__name__)

# Custom Rate Limiters
class NINVerificationRateThrottle(AnonRateThrottle):
    """Rate limiter for NIN verification (anonymous users)."""
    rate = '5/hour'  # 5 attempts per hour for anonymous users

class NINVerificationUserRateThrottle(UserRateThrottle):
    """Rate limiter for NIN verification (authenticated users)."""
    rate = '10/hour'  # 10 attempts per hour for authenticated users

class TokenRefreshRateThrottle(UserRateThrottle):
    """Rate limiter for token refresh."""
    rate = '30/minute'  # 30 refreshes per minute per user

# Custom Exceptions
class NINVerificationError(Exception):
    """Base exception for NIN verification errors."""
    def __init__(self, message: str, code: str = 'verification_failed'):
        self.message = message
        self.code = code
        super().__init__(self.message)

class InvalidNINError(NINVerificationError):
    """Raised when NIN format is invalid."""
    def __init__(self, message: str = 'Invalid NIN format'):
        super().__init__(message, 'invalid_nin')

class InvalidPhoneError(NINVerificationError):
    """Raised when phone number format is invalid."""
    def __init__(self, message: str = 'Invalid phone number format'):
        super().__init__(message, 'invalid_phone')

# Validation Functions
def validate_nin_format(nin: str) -> None:
    """Validate NIN format.
    
    Args:
        nin: NIN to validate
        
    Raises:
        InvalidNINError: If NIN format is invalid
    """
    if not nin or not isinstance(nin, str):
        raise InvalidNINError('NIN is required')
        
    # NIN should be 11 digits
    if not re.match(r'^\d{11}$', nin):
        raise InvalidNINError('NIN must be 11 digits')
        
    # Check if NIN is in blocklist (e.g., test numbers)
    if nin in settings.BLOCKED_NIN_NUMBERS:
        raise InvalidNINError('This NIN is not allowed')

def check_verification_attempts(nin: str, phone: str) -> None:
    """Check if too many verification attempts were made.
    
    Args:
        nin: NIN to check
        phone: Phone number to check
        
    Raises:
        NINVerificationError: If too many attempts were made
    """
    # Check NIN attempts
    nin_key = f'nin_attempts:{nin}'
    nin_attempts = cache.get(nin_key, 0)
    if nin_attempts >= 3:  # Max 3 attempts per NIN
        raise NINVerificationError(
            'Too many verification attempts for this NIN. Please try again later.',
            'too_many_nin_attempts'
        )
        
    # Check phone attempts
    phone_key = f'phone_attempts:{phone}'
    phone_attempts = cache.get(phone_key, 0)
    if phone_attempts >= 3:  # Max 3 attempts per phone
        raise NINVerificationError(
            'Too many verification attempts for this phone number. Please try again later.',
            'too_many_phone_attempts'
        )
        
    # Increment attempt counters
    cache.set(nin_key, nin_attempts + 1, 3600)  # 1 hour expiry
    cache.set(phone_key, phone_attempts + 1, 3600)  # 1 hour expiry

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([NINVerificationRateThrottle, NINVerificationUserRateThrottle])
def verify_nin_and_login(request) -> Response:
    """Verify NIN and generate JWT tokens.
    
    This endpoint:
    1. Validates input format
    2. Checks rate limits
    3. Verifies NIN using VerifyMe API
    4. Creates/updates user account
    5. Generates JWT tokens
    6. Logs authentication attempt
    
    Rate limited to:
    - 5 attempts per hour for anonymous users
    - 10 attempts per hour for authenticated users
    
    Args:
        request: HTTP request containing NIN and phone number.
            {
                "nin": "12345678901",
                "phone": "+2348012345678"
            }
            
    Returns:
        Response containing:
            {
                "accessToken": "jwt.access.token",
                "refreshToken": "jwt.refresh.token",
                "user": {
                    "id": "user.uuid",
                    "email": "user@example.com",
                    ...
                }
            }
            
    Raises:
        400: If input validation fails
        401: If NIN verification fails
        429: If rate limit exceeded
        500: If server error occurs
    """
    try:
        # Validate input
        nin = request.data.get('nin')
        phone = request.data.get('phone')
        
        # Validate NIN format
        try:
            validate_nin_format(nin)
        except InvalidNINError as e:
            return Response(
                {'error': str(e), 'code': e.code},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Format and validate phone number
        try:
            phone = validate_phone_number(phone)
        except Exception as e:
            return Response(
                {'error': str(e), 'code': 'invalid_phone'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check verification attempts
        try:
            check_verification_attempts(nin, phone)
        except NINVerificationError as e:
            return Response(
                {'error': str(e), 'code': e.code},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            
        # Verify NIN
        try:
            verification_result = verify_nin(nin, phone)
        except Exception as e:
            logger.error(f'VerifyMe API error: {str(e)}')
            return Response(
                {'error': 'NIN verification service unavailable', 'code': 'service_unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        if not verification_result['isVerified']:
            # Log failed verification
            AuditLog.objects.create(
                action='NIN_VERIFICATION_FAILED',
                details={
                    'nin': nin,
                    'phone': phone,
                    'reason': verification_result.get('reason', 'Verification failed'),
                    'timestamp': timezone.now().isoformat(),
                    'ip_address': request.META.get('REMOTE_ADDR')
                }
            )
            return Response(
                {
                    'error': 'NIN verification failed',
                    'code': 'verification_failed',
                    'details': verification_result.get('reason')
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        # Get or create user
        try:
            user, created = User.objects.get_or_create(
                nin=nin,
                defaults={
                    'email': f'{nin}@abiahub.ng',  # Temporary email
                    'phone_number': phone,
                    'full_name': verification_result['fullName'],
                    'date_of_birth': verification_result['dateOfBirth'],
                    'gender': verification_result['gender'],
                    'is_active': True,
                    'is_nin_verified': True
                }
            )
            
            if not created:
                # Update user details if changed
                user.phone_number = phone
                user.full_name = verification_result['fullName']
                user.date_of_birth = verification_result['dateOfBirth']
                user.gender = verification_result['gender']
                user.is_nin_verified = True
                user.save()
                
        except Exception as e:
            logger.error(f'User creation/update failed: {str(e)}')
            return Response(
                {'error': 'Failed to create/update user account', 'code': 'user_creation_failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        # Generate tokens
        try:
            refresh = RefreshToken.for_user(user)
        except Exception as e:
            logger.error(f'Token generation failed: {str(e)}')
            return Response(
                {'error': 'Failed to generate authentication tokens', 'code': 'token_generation_failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        # Clear attempt counters on success
        cache.delete(f'nin_attempts:{nin}')
        cache.delete(f'phone_attempts:{phone}')
        
        # Log successful verification
        AuditLog.objects.create(
            action='NIN_VERIFICATION_SUCCESS',
            user=user,
            details={
                'nin': nin,
                'phone': phone,
                'is_new_user': created,
                'timestamp': timezone.now().isoformat(),
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        
        return Response({
            'accessToken': str(refresh.access_token),
            'refreshToken': str(refresh),
            'user': UserSerializer(user).data
        })
        
    except DRFValidationError as e:
        return Response(
            {'error': str(e), 'code': 'validation_error'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f'NIN verification failed: {str(e)}')
        return Response(
            {'error': 'An error occurred during verification', 'code': 'server_error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view with audit logging and rate limiting."""
    
    throttle_classes = [TokenRefreshRateThrottle]
    
    def post(self, request, *args, **kwargs) -> Response:
        """Refresh JWT token.
        
        Rate limited to 30 refreshes per minute per user.
        
        Args:
            request: HTTP request containing refresh token.
                {
                    "refresh": "jwt.refresh.token"
                }
                
        Returns:
            Response containing:
                {
                    "accessToken": "new.jwt.access.token"
                }
                
        Raises:
            401: If refresh token is invalid or expired
            429: If rate limit exceeded
        """
        try:
            response = super().post(request, *args, **kwargs)
            
            # Extract user from refresh token
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    user_id = token.get('user_id')
                    user = User.objects.get(id=user_id)
                    
                    # Log token refresh
                    AuditLog.objects.create(
                        action='TOKEN_REFRESHED',
                        user=user,
                        details={
                            'timestamp': timezone.now().isoformat(),
                            'ip_address': request.META.get('REMOTE_ADDR'),
                            'user_agent': request.META.get('HTTP_USER_AGENT')
                        }
                    )
                except (TokenError, User.DoesNotExist):
                    pass  # Don't fail if we can't log
                    
            return response
            
        except InvalidToken as e:
            # Log invalid token attempt
            AuditLog.objects.create(
                action='TOKEN_REFRESH_FAILED',
                details={
                    'error': str(e),
                    'code': 'invalid_token',
                    'timestamp': timezone.now().isoformat(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                }
            )
            return Response(
                {'error': 'Invalid or expired refresh token', 'code': 'invalid_token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f'Token refresh failed: {str(e)}')
            return Response(
                {'error': 'An error occurred during token refresh', 'code': 'server_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordChangeView(APIView):  
    """Change user password."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        """Handle password change.
        
        Args:
            request: HTTP request containing old and new passwords.
                {
                    "old_password": "old_password",
                    "new_password": "new_password"
                }
        
        Returns:
            Response with success or error message.
        """
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        
        if not old_password or not new_password:
            return Response(
                {"error": "Both old and new passwords are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.check_password(old_password):
            return Response(
                {"error": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        return Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )

class PasswordResetConfirmView(APIView): 
    """Confirm password reset."""
    
    permission_classes = [AllowAny]
    
    def post(self, request: Request) -> Response:
        """Handle password reset confirmation.
        
        Args:
            request: HTTP request containing reset token and new password.
                {
                    "token": "reset_token",
                    "new_password": "new_password"
                }
        
        Returns:
            Response with success or error message.
        """
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        
        if not token or not new_password:
            return Response(
                {"error": "Token and new password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate token (assuming a PasswordReset model)
        from .models import PasswordReset  # Adjust import based on your app
        try:
            reset_request = PasswordReset.objects.get(token=token, expires_at__gt=timezone.now())
            user = reset_request.user
            user.set_password(new_password)
            user.save()
            reset_request.delete()  # Delete the reset request after use
            
            return Response(
                {"message": "Password reset successfully"},
                status=status.HTTP_200_OK
            )
        except PasswordReset.DoesNotExist:
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST
            )


class PasswordResetRequestView(APIView):
    """Request password reset."""
    
    permission_classes = [AllowAny]
    
    def post(self, request: Request) -> Response:
        """Handle password reset request.
        
        Args:
            request: HTTP request containing email.
                {
                    "email": "user@example.com"
                }
        
        Returns:
            Response with success or error message.
        """
        email = request.data.get("email")
        
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if the email exists
            return Response(
                {"message": "If the email exists, a reset link/code will be sent"},
                status=status.HTTP_200_OK
            )
        
        # Generate a unique reset token
        reset_token = str(uuid.uuid4())
        
        # Save token (assuming a PasswordReset model)
        from .models import PasswordReset  # Adjust import based on your app
        PasswordReset.objects.create(
            user=user,
            token=reset_token,
            expires_at=timezone.now() + timezone.timedelta(hours=1)  # 1-hour expiry
        )
        
        # Option 1: Send reset link via email
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
        try:
            send_mail(
                subject="Password Reset Request",
                message=f"Click to reset your password: {reset_link}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info(f"Password reset email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send reset email to {email}: {str(e)}")
            return Response(
                {"error": "Failed to send reset email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Option 2: Send reset subscribed via SMS (using AfricasTalkingClient)
        if hasattr(user, 'phone_number') and user.phone_number:
            try:
                client = AfricasTalkingClient()
                reset_code = reset_token[:6]  # Short code for SMS
                sms_message = f"Your password reset code is: {reset_code}"
                sms_response = client.send_sms(to=user.phone_number, message=sms_message)
                
                if sms_response["status"] == "error":
                    logger.error(f"Failed to send SMS to {user.phone_number}: {sms_response['message']}")
                else:
                    logger.info(f"Password reset SMS sent to {user.phone_number}")
            except Exception as e:
                logger.error(f"Failed to send reset SMS: {str(e)}")
                # Continue even if SMS fails, as email was sent
                pass
        
        return Response(
            {"message": "If the email exists, a reset link/code will be sent"},
            status=status.HTTP_200_OK
        )
        
        
class LogoutView(APIView):  
    
    """Logout user and blacklist refresh token."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        """Handle user logout.
        
        Args:
            request: HTTP request containing refresh token.
                {
                    "refresh": "jwt.refresh.token"
                }
        
        Returns:
            Response with success or error message.
        """
        refresh_token = request.data.get("refresh")
        
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Log logout action
            AuditLog.objects.create(
                action='USER_LOGOUT',
                user=request.user,
                details={
                    'timestamp': timezone.now().isoformat(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                }
            )
            
            return Response(
                {"message": "Logged out successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f'Logout failed: {str(e)}')
            return Response(
                {'error': 'Failed to log out', 'code': 'logout_failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class health_check(APIView):
    """Health check endpoint."""
    
    permission_classes = [AllowAny]
    
    def get(self, request: Request) -> Response:
        """Handle health check.
        
        Returns:
            Response with status 200 OK.
        """
        return Response(
            {"status": "ok"},
            status=status.HTTP_200_OK
        )
        

class api_documentation(APIView):  
    """API documentation endpoint."""
    
    permission_classes = [AllowAny]
    
    def get(self, request: Request) -> Response:
        """Handle API documentation request.
        
        Returns:
            Response with API documentation.
        """
        return Response(
            {
                "message": "API documentation is available at /api/docs/"
            },
            status=status.HTTP_200_OK
        )