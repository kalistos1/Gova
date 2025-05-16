from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from core.models import BaseModel

class User(AbstractUser, BaseModel):
    """Custom user model with additional fields for state officials and citizens.
    
    This model extends Django's AbstractUser to add custom fields and functionality
    specific to the AbiaHub platform.
    """
    
    # Remove username field and use email as the unique identifier
    username = None
    email = models.EmailField(
        _('email address'),
        unique=True,
        help_text=_('User\'s email address (used for login)')
    )
    
    # Additional fields
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message=_('Phone number must be entered in the format: +234XXXXXXXXXX')
    )
    phone_number = models.CharField(
        _('phone number'),
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text=_('User\'s phone number')
    )
    is_state_official = models.BooleanField(
        _('state official status'),
        default=False,
        help_text=_('Whether the user is a state official')
    )
    is_lga_official = models.BooleanField(
        _('LGA official status'),
        default=False,
        help_text=_('Whether the user is an LGA official')
    )
    department = models.CharField(
        _('department'),
        max_length=100,
        blank=True,
        help_text=_('Department or unit (for officials)')
    )
    position = models.CharField(
        _('position'),
        max_length=100,
        blank=True,
        help_text=_('Position or role (for officials)')
    )
    
    # Set email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_state_official']),
            models.Index(fields=['is_lga_official']),
        ]
        
    def __str__(self):
        """Return string representation of the user."""
        return self.get_full_name() or self.email
        
    @property
    def is_official(self) -> bool:
        """Check if user is any type of official.
        
        Returns:
            bool: True if user is a state or LGA official, False otherwise.
        """
        return self.is_state_official or self.is_lga_official
        
    def get_full_name(self) -> str:
        """Get user's full name.
        
        Returns:
            str: User's full name or empty string if not set.
        """
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else ''
        
    def get_short_name(self) -> str:
        """Get user's short name.
        
        Returns:
            str: User's first name or email if not set.
        """
        return self.first_name or self.email
