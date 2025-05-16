"""Forms for engagement management.

This module provides Django forms for:
- Creating messages (text and voice)
- Creating notifications
- Recipient group selection
- Voice file validation
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator

from core.models import Location, Landmark
from .models import Message, Notification, RecipientGroup

User = get_user_model()

class MessageForm(forms.ModelForm):
    """Form for creating messages.
    
    This form handles:
    - Text messages
    - Voice recordings
    - Location/landmark selection
    - Voice transcription
    
    Attributes:
        query (TextField): Message content
        voice_data (FileField): Voice recording
        location (ModelChoiceField): Related location
        landmark (ModelChoiceField): Related landmark
        language (ChoiceField): Voice transcription language
    """
    
    voice_data = forms.FileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['mp3', 'wav', 'ogg', 'm4a'],
                message=_('Only MP3, WAV, OGG, and M4A files are allowed.')
            )
        ],
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': 'audio/mp3,audio/wav,audio/ogg,audio/m4a'
            }
        ),
        help_text=_('Voice recording (optional, max 10MB)')
    )
    
    language = forms.ChoiceField(
        choices=[
            ('en', _('English')),
            ('ig', _('Igbo')),
            ('pidgin', _('Pidgin English'))
        ],
        initial='en',
        required=False,
        widget=forms.Select(
            attrs={'class': 'form-select'}
        ),
        help_text=_('Language for voice transcription')
    )
    
    class Meta:
        model = Message
        fields = ['query', 'location', 'landmark']
        widgets = {
            'query': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': _('Type your message here...')
                }
            ),
            'location': forms.Select(
                attrs={
                    'class': 'form-select',
                    'placeholder': _('Select a location')
                }
            ),
            'landmark': forms.Select(
                attrs={
                    'class': 'form-select',
                    'placeholder': _('Select a landmark')
                }
            )
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic querysets."""
        super().__init__(*args, **kwargs)
        
        # Update location choices
        self.fields['location'].queryset = Location.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Update landmark choices based on selected location
        if self.instance and self.instance.location:
            self.fields['landmark'].queryset = Landmark.objects.filter(
                location=self.instance.location,
                is_active=True
            ).order_by('name')
        else:
            self.fields['landmark'].queryset = Landmark.objects.none()
            
    def clean_voice_data(self):
        """Validate voice recording file.
        
        Returns:
            UploadedFile: Validated voice file
            
        Raises:
            ValidationError: If file is too large or invalid
        """
        voice_file = self.cleaned_data.get('voice_data')
        if voice_file:
            # Check file size (10MB max)
            if voice_file.size > 10 * 1024 * 1024:
                raise ValidationError(
                    _('Voice recording must be less than 10MB.')
                )
                
            # Check content type
            content_type = voice_file.content_type
            if not content_type.startswith('audio/'):
                raise ValidationError(
                    _('Invalid file type. Only audio files are allowed.')
                )
                
        return voice_file
        
    def clean(self):
        """Validate form data.
        
        Returns:
            dict: Cleaned form data
            
        Raises:
            ValidationError: If validation fails
        """
        cleaned_data = super().clean()
        
        # Check content
        query = cleaned_data.get('query')
        voice_data = cleaned_data.get('voice_data')
        
        if not query and not voice_data:
            raise ValidationError(
                _('Either message text or voice recording must be provided.')
            )
            
        # Check location/landmark
        location = cleaned_data.get('location')
        landmark = cleaned_data.get('landmark')
        
        if not location and not landmark:
            raise ValidationError(
                _('Either location or landmark must be provided.')
            )
            
        if landmark and location and landmark.location != location:
            raise ValidationError(
                _('Selected landmark does not belong to selected location.')
            )
            
        return cleaned_data

class NotificationForm(forms.ModelForm):
    """Form for creating notifications.
    
    This form handles:
    - Notification details
    - Target selection
    - Priority levels
    - Group selection
    
    Attributes:
        title (CharField): Notification title
        message (TextField): Notification content
        target_type (ChoiceField): Target type (user/group)
        target_id (UUIDField): Target user/group ID
        priority (ChoiceField): Notification priority
    """
    
    class Meta:
        model = Notification
        fields = ['title', 'message', 'target_type', 'target_id', 'priority']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': _('Enter notification title')
                }
            ),
            'message': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': _('Enter notification message')
                }
            ),
            'target_type': forms.Select(
                attrs={'class': 'form-select'},
                choices=Notification.TargetType.choices
            ),
            'target_id': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'priority': forms.Select(
                attrs={'class': 'form-select'},
                choices=Notification.Priority.choices
            )
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic querysets."""
        super().__init__(*args, **kwargs)
        
        # Update target choices based on target type
        target_type = self.data.get('target_type')
        if target_type == 'user':
            self.fields['target_id'].queryset = User.objects.filter(
                is_active=True
            ).order_by('username')
            self.fields['target_id'].label = _('Select User')
        elif target_type == 'group':
            self.fields['target_id'].queryset = RecipientGroup.objects.filter(
                is_active=True
            ).order_by('name')
            self.fields['target_id'].label = _('Select Group')
        else:
            self.fields['target_id'].queryset = User.objects.none()
            
    def clean_title(self):
        """Validate notification title.
        
        Returns:
            str: Validated title
            
        Raises:
            ValidationError: If title is too short
        """
        title = self.cleaned_data.get('title')
        if len(title.strip()) < 5:
            raise ValidationError(
                _('Title must be at least 5 characters long.')
            )
        return title
        
    def clean_message(self):
        """Validate notification message.
        
        Returns:
            str: Validated message
            
        Raises:
            ValidationError: If message is too short
        """
        message = self.cleaned_data.get('message')
        if len(message.strip()) < 10:
            raise ValidationError(
                _('Message must be at least 10 characters long.')
            )
        return message
        
    def clean(self):
        """Validate form data.
        
        Returns:
            dict: Cleaned form data
            
        Raises:
            ValidationError: If validation fails
        """
        cleaned_data = super().clean()
        
        # Check target type and ID
        target_type = cleaned_data.get('target_type')
        target_id = cleaned_data.get('target_id')
        
        if target_type == 'user':
            if not User.objects.filter(id=target_id, is_active=True).exists():
                raise ValidationError(
                    _('Selected user does not exist or is inactive.')
                )
        elif target_type == 'group':
            if not RecipientGroup.objects.filter(id=target_id, is_active=True).exists():
                raise ValidationError(
                    _('Selected group does not exist or is inactive.')
                )
                
        return cleaned_data 