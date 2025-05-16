from django.db import models
# from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinLengthValidator
from django.conf import settings
import uuid
import json
from django.core.serializers.json import DjangoJSONEncoder

User = get_user_model()

class Report(models.Model):
    """Model for citizen issue reports in Abia State.

    This model stores reports submitted by citizens about various issues in their LGA,
    including infrastructure problems, security concerns, and public service issues.
    """

    CATEGORY_CHOICES = [
        ('INFRASTRUCTURE', 'Infrastructure'),
        ('SECURITY', 'Security'),
        ('HEALTH', 'Healthcare'),
        ('EDUCATION', 'Education'),
        ('ENVIRONMENT', 'Environment'),
        ('UTILITIES', 'Public Utilities'),
        ('CORRUPTION', 'Corruption'),
        ('OTHER', 'Other'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('NOT_REQUIRED', 'Payment Not Required'),
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Payment Completed'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Payment Refunded'),
    ]

    SUBMISSION_CHANNEL_CHOICES = [
        ('WEB', 'Web Dashboard'),
        ('MOBILE', 'Mobile App'),
        ('USSD', 'USSD'),
        ('SMS', 'SMS'),
        ('WHATSAPP', 'WhatsApp'),
        ('KIOSK', 'Physical Kiosk'),
        ('VOICE', 'Voice Call'),
    ]

    # Primary Fields
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique identifier for the report')
    )
    title = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(10)],
        help_text=_('Brief title describing the issue')
    )
    description = models.TextField(
        validators=[MinLengthValidator(50)],
        help_text=_('Detailed description of the issue')
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text=_('Category of the reported issue')
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        help_text=_('Priority level of the issue')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text=_('Current status of the report')
    )

    # Location Information
    # location = gis_models.PointField(
    #     help_text=_('Geographic location of the reported issue'),
    #     null=True,
    #     blank=True,
    # )
    location = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Geographic location of the reported issue (latitude, longitude)')
    )
    
    address = models.CharField(
        max_length=255,
        help_text=_('Physical address of the issue location')
    )
    lga = models.ForeignKey(
        'core.LGA',
        on_delete=models.PROTECT,
        help_text=_('Local Government Area where the issue was reported')
    )
    landmark = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Nearby landmark for easier location identification')
    )

    # Media
    images = models.JSONField(
        null=True,
        blank=True,
        help_text=_('List of image URLs related to the issue'),
        encoder=DjangoJSONEncoder
    )
    videos = models.JSONField(
        null=True,
        blank=True,
        help_text=_('List of video URLs related to the issue'),
        encoder=DjangoJSONEncoder
    )
    voice_notes = models.JSONField(
        null=True,
        blank=True,
        help_text=_('List of voice note URLs related to the issue'),
        encoder=DjangoJSONEncoder
    )

    # Metadata
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
        help_text=_('User who submitted the report')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Timestamp when the report was created')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_('Timestamp when the report was last updated')
    )
    is_anonymous = models.BooleanField(
        default=False,
        help_text=_('Whether the report was submitted anonymously')
    )
    upvotes = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of upvotes the report has received')
    )
    ai_summary = models.TextField(
        null=True,
        blank=True,
        help_text=_('AI-generated summary of the report')
    )
    ai_priority_score = models.FloatField(
        null=True,
        blank=True,
        help_text=_('AI-generated priority score (0-1)')
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_reports',
        help_text=_('Government official assigned to handle this report')
    )

    # Submission Information
    submission_channel = models.CharField(
        max_length=20,
        choices=SUBMISSION_CHANNEL_CHOICES,
        default='WEB',
        help_text=_('Channel through which the report was submitted')
    )
    submission_language = models.CharField(
        max_length=10,
        default='en',
        help_text=_('Language used for submission (en, ig, pcm)')
    )
    original_text = models.TextField(
        null=True,
        blank=True,
        help_text=_('Original text before translation if applicable')
    )
    device_info = models.JSONField(
        null=True,
        blank=True,
        help_text=_('Device information for mobile/web submissions'),
        encoder=DjangoJSONEncoder
    )
    offline_sync_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_('ID for tracking offline submissions')
    )

    # Payment Information
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='NOT_REQUIRED',
        help_text=_('Status of any required payment for this report')
    )
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Amount required for payment, if applicable')
    )
    transaction_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Flutterwave transaction reference')
    )
    transaction_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Flutterwave transaction ID')
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the payment was completed')
    )

    # Verification Information
    nin_verified = models.BooleanField(
        default=False,
        help_text=_('Whether the reporter\'s NIN has been verified')
    )
    nin_verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the NIN was verified')
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['lga']),
            models.Index(fields=['created_at']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['submission_channel']),
            models.Index(fields=['offline_sync_id']),
        ]
        verbose_name = _('Issue Report')
        verbose_name_plural = _('Issue Reports')

    def __str__(self):
        """Return a string representation of the report."""
        return f'{self.title} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        """Override save method to handle custom logic."""
        # If this is a new report (no ID yet)
        if not self.id:
            # Set reporter to None if anonymous
            if self.is_anonymous:
                self.reporter = None
            
            # Extract location from image EXIF if available
            if self.images and not self.location:
                from .utils import extract_location_from_exif
                self.location = extract_location_from_exif(self.images[0])

            # Generate AI summary and priority if enabled
            if settings.ENABLE_AI_PROCESSING:
                from .utils import generate_ai_summary, calculate_ai_priority
                self.ai_summary = generate_ai_summary(self.description)
                self.ai_priority_score = calculate_ai_priority(self.description)
                
                # Update priority based on AI score
                if self.ai_priority_score:
                    if self.ai_priority_score >= 0.8:
                        self.priority = 'URGENT'
                    elif self.ai_priority_score >= 0.6:
                        self.priority = 'HIGH'
                    elif self.ai_priority_score >= 0.4:
                        self.priority = 'MEDIUM'
                    else:
                        self.priority = 'LOW'

        super().save(*args, **kwargs)

    @property
    def is_offline_submission(self):
        """Check if this was submitted through an offline channel."""
        return self.submission_channel in ['USSD', 'SMS', 'KIOSK']

    @property
    def requires_translation(self):
        """Check if the report needs translation."""
        return self.submission_language != 'en'

    @property
    def resolution_time(self):
        """Calculate time taken to resolve the issue."""
        if self.status == 'RESOLVED':
            return self.updated_at - self.created_at
        return None

class ReportComment(models.Model):
    """Model for comments on reports."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_official = models.BooleanField(
        default=False,
        help_text=_('Whether this is an official response')
    )
    
    class Meta:
        ordering = ['created_at']
        verbose_name = _('Report Comment')
        verbose_name_plural = _('Report Comments')

class AuditLog(models.Model):
    """Model for tracking changes to reports.
    
    This model stores an audit trail of all changes made to reports,
    including status updates, assignments, and payment status changes.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique identifier for the audit log entry')
    )
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text=_('Report that was modified')
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text=_('User who made the change')
    )
    
    action = models.CharField(
        max_length=50,
        help_text=_('Type of change made')
    )
    
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text=_('Previous value before change'),
        encoder=DjangoJSONEncoder
    )
    
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text=_('New value after change'),
        encoder=DjangoJSONEncoder
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_('IP address of user who made the change')
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text=_('User agent of browser/client that made the change')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When the change was made')
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Audit Log Entry')
        verbose_name_plural = _('Audit Log Entries')
        indexes = [
            models.Index(fields=['report', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action']),
        ]
        
    def __str__(self):
        """Return a string representation of the audit log entry."""
        return f'{self.action} on {self.report} by {self.user or "System"}'
