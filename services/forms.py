"""Forms for service request management.

This module provides Django forms for:
- Creating service requests
- Updating request status and payment status
- Location/landmark selection
- Payment validation
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from core.models import Location, Landmark
from .models import Service, ServiceRequest

User = get_user_model()

class ServiceRequestForm(forms.ModelForm):
    """Form for creating service requests.
    
    This form handles:
    - Service selection
    - Location and landmark selection
    - Payment validation
    - Status management
    
    Attributes:
        service (ModelChoiceField): Selected service
        location (ModelChoiceField): Service location
        landmark (ModelChoiceField): Nearest landmark
        amount (DecimalField): Payment amount
    """
    
    class Meta:
        model = ServiceRequest
        fields = ['service', 'location', 'landmark', 'amount']
        widgets = {
            'service': forms.Select(
                attrs={
                    'class': 'form-select',
                    'placeholder': _('Select a service')
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
            ),
            'amount': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': _('Enter amount in NGN'),
                    'min': '0',
                    'step': '0.01'
                }
            )
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic querysets."""
        super().__init__(*args, **kwargs)
        
        # Update service choices
        self.fields['service'].queryset = Service.objects.filter(
            is_active=True
        ).order_by('name')
        
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
            
    def clean_amount(self):
        """Validate payment amount against service base price.
        
        Returns:
            decimal.Decimal: Validated amount
            
        Raises:
            ValidationError: If amount is less than service base price
        """
        amount = self.cleaned_data.get('amount')
        service = self.cleaned_data.get('service')
        
        if service and amount < service.base_price:
            raise ValidationError(
                _('Amount must be at least %(price)s NGN.'),
                params={'price': service.base_price}
            )
            
        return amount
        
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

class ServiceRequestStatusForm(forms.ModelForm):
    """Form for updating service request status and payment status.
    
    This form is used by state officials to:
    - Update request status
    - Update payment status
    - Add status notes
    
    Attributes:
        status (ChoiceField): Request status
        payment_status (ChoiceField): Payment status
        notes (TextField): Optional status update note
    """
    
    notes = forms.CharField(
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
        model = ServiceRequest
        fields = ['status', 'payment_status']
        widgets = {
            'status': forms.Select(
                attrs={'class': 'form-select'},
                choices=ServiceRequest.Status.choices
            ),
            'payment_status': forms.Select(
                attrs={'class': 'form-select'},
                choices=ServiceRequest.PaymentStatus.choices
            )
        }
        
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
        payment_status = cleaned_data.get('payment_status')
        
        if self.instance:
            old_status = self.instance.status
            old_payment_status = self.instance.payment_status
            
            # Validate status transitions
            if status != old_status:
                if old_status == ServiceRequest.Status.COMPLETED:
                    raise ValidationError(
                        _('Cannot change status of a completed request.')
                    )
                if old_status == ServiceRequest.Status.CANCELLED:
                    raise ValidationError(
                        _('Cannot change status of a cancelled request.')
                    )
                    
            # Validate payment status transitions
            if payment_status != old_payment_status:
                if old_payment_status == ServiceRequest.PaymentStatus.PAID:
                    raise ValidationError(
                        _('Cannot change payment status of a paid request.')
                    )
                    
            # Validate status and payment status combinations
            if status == ServiceRequest.Status.COMPLETED:
                if payment_status != ServiceRequest.PaymentStatus.PAID:
                    raise ValidationError(
                        _('Request cannot be completed without payment.')
                    )
                    
            if status == ServiceRequest.Status.CANCELLED:
                if payment_status == ServiceRequest.PaymentStatus.PAID:
                    raise ValidationError(
                        _('Cannot cancel a paid request without refund.')
                    )
                    
            if payment_status == ServiceRequest.PaymentStatus.REFUNDED:
                if status not in [
                    ServiceRequest.Status.CANCELLED,
                    ServiceRequest.Status.REJECTED
                ]:
                    raise ValidationError(
                        _('Refund is only allowed for cancelled or rejected requests.')
                    )
                    
        return cleaned_data 