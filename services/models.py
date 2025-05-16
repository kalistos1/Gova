from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.conf import settings
from core.models import BaseModel, Location, Landmark
from django.utils import timezone
from django.core.exceptions import ValidationError

class Service(BaseModel):
    """Model for government services offered to citizens.
    
    This model represents services that can be requested by citizens through
    the platform. Each service has a base price and can be categorized.
    """
    
    class Category(models.TextChoices):
        """Service categories."""
        DOCUMENTATION = 'documentation', _('Documentation')
        PERMIT = 'permit', _('Permit')
        CERTIFICATE = 'certificate', _('Certificate')
        LICENSE = 'license', _('License')
        CLEARANCE = 'clearance', _('Clearance')
        REGISTRATION = 'registration', _('Registration')
        OTHER = 'other', _('Other')
    
    name = models.CharField(
        _('service name'),
        max_length=100,
        help_text=_('Name of the service')
    )
    description = models.TextField(
        _('description'),
        help_text=_('Detailed description of the service')
    )
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
        help_text=_('Category of the service')
    )
    base_price = models.DecimalField(
        _('base price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Base price for the service in NGN')
    )
    is_active = models.BooleanField(
        _('active status'),
        default=True,
        help_text=_('Whether the service is currently available')
    )
    
    class Meta:
        verbose_name = _('service')
        verbose_name_plural = _('services')
        ordering = ['name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
        
    def __str__(self):
        """Return string representation of the service."""
        return self.name
        
    @property
    def is_available(self) -> bool:
        """Check if the service is currently available.
        
        Returns:
            bool: True if service is active, False otherwise.
        """
        return self.is_active

class ServiceRequest(BaseModel):
    """Model for service requests made by citizens.
    
    This model tracks service requests, their status, and payment information.
    Each request is linked to a service, location, and landmark.
    """
    
    class Status(models.TextChoices):
        """Service request statuses."""
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        REJECTED = 'rejected', _('Rejected')
    
    class PaymentStatus(models.TextChoices):
        """Payment statuses."""
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='service_requests',
        verbose_name=_('requester'),
        help_text=_('User who requested the service')
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='requests',
        verbose_name=_('service'),
        help_text=_('Requested service')
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='service_requests',
        verbose_name=_('location'),
        help_text=_('Location where service is needed')
    )
    landmark = models.ForeignKey(
        Landmark,
        on_delete=models.PROTECT,
        related_name='service_requests',
        verbose_name=_('landmark'),
        help_text=_('Nearest landmark to service location')
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Amount paid for the service in NGN')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_('Current status of the request')
    )
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        help_text=_('Current payment status')
    )
    payment_reference = models.CharField(
        _('payment reference'),
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Unique reference for the payment')
    )
    payment_link = models.URLField(
        _('payment link'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Link to complete payment')
    )
    notes = models.TextField(
        _('notes'),
        blank=True,
        help_text=_('Additional notes about the request')
    )
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
        help_text=_('When the request was completed')
    )
    
    class Meta:
        verbose_name = _('service request')
        verbose_name_plural = _('service requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['service', 'status']),
        ]
        
    def __str__(self):
        """Return string representation of the service request."""
        return f'{self.service.name} - {self.user.get_full_name() or self.user.username}'
        
    @property
    def is_paid(self) -> bool:
        """Check if the request has been paid for.
        
        Returns:
            bool: True if payment status is paid, False otherwise.
        """
        return self.payment_status == self.PaymentStatus.PAID
        
    @property
    def is_completed(self) -> bool:
        """Check if the request has been completed.
        
        Returns:
            bool: True if status is completed, False otherwise.
        """
        return self.status == self.Status.COMPLETED
        
    @property
    def is_cancellable(self) -> bool:
        """Check if the request can be cancelled.
        
        Returns:
            bool: True if request can be cancelled, False otherwise.
        """
        return self.status in [self.Status.PENDING, self.Status.PROCESSING]
        
    def complete(self, save: bool = True) -> None:
        """Mark the request as completed.
        
        Args:
            save: Whether to save the model after updating.
        """
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if save:
            self.save()
            
    def cancel(self, save: bool = True) -> None:
        """Cancel the request if possible.
        
        Args:
            save: Whether to save the model after updating.
            
        Raises:
            ValidationError: If request cannot be cancelled.
        """
        if not self.is_cancellable:
            raise ValidationError(_('This request cannot be cancelled.'))
        self.status = self.Status.CANCELLED
        if save:
            self.save()
            
    def mark_as_paid(self, save: bool = True) -> None:
        """Mark the request as paid.
        
        Args:
            save: Whether to save the model after updating.
        """
        self.payment_status = self.PaymentStatus.PAID
        if save:
            self.save()
            
    def refund(self, save: bool = True) -> None:
        """Mark the request as refunded.
        
        Args:
            save: Whether to save the model after updating.
        """
        self.payment_status = self.PaymentStatus.REFUNDED
        if save:
            self.save()
