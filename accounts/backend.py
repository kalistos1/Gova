"""Custom authentication backend for email-based login."""

import logging
from typing import Optional
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

UserModel = get_user_model()
logger = logging.getLogger(__name__)

class EmailBackend(ModelBackend):
    """Custom authentication backend to allow login with either username or email.
    
    This backend extends Django's ModelBackend to:
    1. Allow login with either username or email
    2. Handle case-insensitive matching
    3. Provide proper error handling and logging
    4. Enforce security checks
    """
    
    def authenticate(
        self,
        request,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ) -> Optional[UserModel]:
        """Authenticate a user by email/username and password.
        
        Args:
            request: The HTTP request
            username: The username or email to authenticate with
            password: The password to authenticate with
            **kwargs: Additional arguments
            
        Returns:
            Optional[UserModel]: The authenticated user or None
            
        Raises:
            ValidationError: If authentication data is invalid
        """
        try:
            # Validate input
            if not username:
                raise ValidationError(_('Username/email is required.'))
            if not password:
                raise ValidationError(_('Password is required.'))
                
            # Clean username/email
            username = username.strip().lower()
            
            # Get user by username or email
            try:
                user = UserModel.objects.get(
                    Q(username__iexact=username) |
                    Q(email__iexact=username)
                )
            except UserModel.DoesNotExist:
                # Log failed login attempt
                logger.warning(
                    'Login failed: User not found',
                    extra={
                        'username': username,
                        'ip': request.META.get('REMOTE_ADDR') if request else None
                    }
                )
                return None
            except UserModel.MultipleObjectsReturned:
                # Handle rare case of duplicate users
                logger.error(
                    'Multiple users found with same username/email',
                    extra={
                        'username': username,
                        'ip': request.META.get('REMOTE_ADDR') if request else None
                    }
                )
                user = UserModel.objects.filter(
                    Q(username__iexact=username) |
                    Q(email__iexact=username)
                ).order_by('id').first()
                
            # Check password and user status
            if user and user.check_password(password):
                if not self.user_can_authenticate(user):
                    # Log inactive user attempt
                    logger.warning(
                        'Login failed: User inactive',
                        extra={
                            'user_id': user.id,
                            'username': username,
                            'ip': request.META.get('REMOTE_ADDR') if request else None
                        }
                    )
                    raise ValidationError(_('This account is inactive.'))
                    
                # Log successful login
                logger.info(
                    'Login successful',
                    extra={
                        'user_id': user.id,
                        'username': username,
                        'ip': request.META.get('REMOTE_ADDR') if request else None
                    }
                )
                return user
                
            # Log failed password attempt
            logger.warning(
                'Login failed: Invalid password',
                extra={
                    'user_id': user.id if user else None,
                    'username': username,
                    'ip': request.META.get('REMOTE_ADDR') if request else None
                }
            )
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error(
                'Authentication error',
                extra={
                    'error': str(e),
                    'username': username,
                    'ip': request.META.get('REMOTE_ADDR') if request else None
                },
                exc_info=True
            )
            return None
            
    def get_user(self, user_id: int) -> Optional[UserModel]:
        """Get user by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[UserModel]: The user or None if not found
        """
        try:
            user = UserModel.objects.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except UserModel.DoesNotExist:
            return None
        except Exception as e:
            logger.error(
                'Error getting user',
                extra={
                    'error': str(e),
                    'user_id': user_id
                },
                exc_info=True
            )
            return None
