"""Forms for report management.

This module provides Django forms for:
- Creating and updating reports
- Updating report status and assignments
- Media file validation
- Location/landmark selection
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from core.models import Location, Landmark
from .models import Report

User = get_user_model()

class ReportForm(forms.ModelForm):
    """Form for creating and updating reports.
    
    This form handles:
    - Report details (title, description, category)
    - Location and landmark selection
    - Media file upload with validation
    - EXIF data extraction for location
    
    Attributes:
        title (CharField): Report title
        description (TextField): Detailed report description
        category (ChoiceField): Report category
        location (ModelChoiceField): Related location
        landmark (ModelChoiceField): Related landmark
        media (FileField): Image/video upload
    """
    
    # Custom fields
    media = forms.FileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'mp4', 'mov'],
                message=_('Only JPG, PNG, MP4 and MOV files are allowed.')
            )
        ],
        help_text=_('Upload an image or video (max 10MB)')
    )
    
    class Meta:
        model = Report
        fields = [
            'title', 'description', 'category',
            'location', 'landmark', 'media'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': _('Enter report title')
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 5,
                    'placeholder': _('Describe the issue in detail')
                }
            ),
            'category': forms.Select(
                attrs={'class': 'form-select'},
                choices=Report.CATEGORY_CHOICES
            ),
            'location': forms.Select(
                attrs={'class': 'form-select'},
                queryset=Location.objects.filter(is_active=True)
            ),
            'landmark': forms.Select(
                attrs={'class': 'form-select'},
                queryset=Landmark.objects.filter(is_active=True)
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
            
    def clean_media(self):
        """Validate uploaded media file.
        
        Returns:
            UploadedFile: Validated media file
            
        Raises:
            ValidationError: If file is too large or invalid type
        """
        media = self.cleaned_data.get('media')
        if not media:
            return None
            
        # Check file size (10MB max)
        if media.size > 10 * 1024 * 1024:
            raise ValidationError(
                _('File size must be no more than 10MB.')
            )
            
        # Check content type
        content_type = media.content_type
        if content_type.startswith('image/'):
            # Validate image dimensions
            from PIL import Image
            try:
                img = Image.open(media)
                width, height = img.size
                if width > 4096 or height > 4096:
                    raise ValidationError(
                        _('Image dimensions must be no more than 4096x4096 pixels.')
                    )
            except Exception as e:
                raise ValidationError(
                    _('Invalid image file: %(error)s'),
                    params={'error': str(e)}
                )
        elif content_type.startswith('video/'):
            # TODO: Add video validation (duration, codec, etc.)
            pass
        else:
            raise ValidationError(
                _('Invalid file type. Only images and videos are allowed.')
            )
            
        return media
        
    def clean(self):
        """Validate form data.
        
        Returns:
            dict: Cleaned form data
            
        Raises:
            ValidationError: If validation fails
        """
        cleaned_data = super().clean()
        
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

class ReportStatusForm(forms.ModelForm):
    """Form for updating report status and assignment.
    
    This form is used by LGA officials to:
    - Update report status
    - Assign reports to officials
    - Add status notes
    
    Attributes:
        status (ChoiceField): Report status
        assigned_to (ModelChoiceField): Assigned official
        status_note (TextField): Optional status update note
    """
    
    status_note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Add a note about this status update')
            }
        ),
        help_text=_('Optional note explaining the status change')
    )
    
    class Meta:
        model = Report
        fields = ['status', 'assigned_to']
        widgets = {
            'status': forms.Select(
                attrs={'class': 'form-select'},
                choices=Report.STATUS_CHOICES
            ),
            'assigned_to': forms.Select(
                attrs={'class': 'form-select'}
            )
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with filtered querysets."""
        super().__init__(*args, **kwargs)
        
        # Filter assigned_to choices to LGA officials
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_active=True,
            is_lga_official=True
        ).order_by('first_name', 'last_name')
        
    def clean(self):
        """Validate form data.
        
        Returns:
            dict: Cleaned form data
            
        Raises:
            ValidationError: If validation fails
        """
        cleaned_data = super().clean()
        
        # Check status transitions
        status = cleaned_data.get('status')
        assigned_to = cleaned_data.get('assigned_to')
        
        if status == 'in_progress' and not assigned_to:
            raise ValidationError(
                _('Report must be assigned when status is "In Progress".')
            )
            
        if status == 'completed' and not self.cleaned_data.get('status_note'):
            raise ValidationError(
                _('Status note is required when marking report as completed.')
            )
            
        return cleaned_data 