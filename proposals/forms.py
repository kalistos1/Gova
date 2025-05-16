"""Forms for proposal management.

This module provides Django forms for:
- Creating and updating proposals
- Submitting votes on proposals
- Location/landmark selection
- Vote validation
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.models import Location, Landmark
from .models import Proposal, Vote

class ProposalForm(forms.ModelForm):
    """Form for creating and updating proposals.
    
    This form handles:
    - Proposal details (title, description, category)
    - Location and landmark selection
    - Status management
    - Validation rules
    
    Attributes:
        title (CharField): Proposal title
        description (TextField): Detailed proposal description
        category (ChoiceField): Proposal category
        location (ModelChoiceField): Related location
        landmark (ModelChoiceField): Related landmark
        status (ChoiceField): Proposal status
    """
    
    class Meta:
        model = Proposal
        fields = [
            'title', 'description', 'category',
            'location', 'landmark', 'status'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': _('Enter proposal title')
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 5,
                    'placeholder': _('Describe your proposal in detail')
                }
            ),
            'category': forms.Select(
                attrs={'class': 'form-select'},
                choices=Proposal.Category.choices
            ),
            'location': forms.Select(
                attrs={'class': 'form-select'},
                queryset=Location.objects.filter(is_active=True)
            ),
            'landmark': forms.Select(
                attrs={'class': 'form-select'},
                queryset=Landmark.objects.filter(is_active=True)
            ),
            'status': forms.Select(
                attrs={'class': 'form-select'},
                choices=Proposal.Status.choices
            )
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic querysets and status choices."""
        self.user = kwargs.pop('user', None)
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
            
        # Limit status choices based on user role
        if not self.user or not self.user.is_staff:
            self.fields['status'].choices = [
                (status, label) for status, label in Proposal.Status.choices
                if status in ['draft', 'active']
            ]
            
    def clean_title(self):
        """Validate proposal title.
        
        Returns:
            str: Validated title
            
        Raises:
            ValidationError: If title is too short
        """
        title = self.cleaned_data.get('title')
        if len(title) < 10:
            raise ValidationError(
                _('Title must be at least 10 characters long.')
            )
        return title
        
    def clean_description(self):
        """Validate proposal description.
        
        Returns:
            str: Validated description
            
        Raises:
            ValidationError: If description is too short
        """
        description = self.cleaned_data.get('description')
        if len(description) < 50:
            raise ValidationError(
                _('Description must be at least 50 characters long.')
            )
        return description
        
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
            
        # Check status transitions
        if self.instance and self.instance.pk:
            old_status = self.instance.status
            new_status = cleaned_data.get('status')
            
            if old_status != new_status:
                # Only allow draft -> active transition for non-staff
                if not self.user or not self.user.is_staff:
                    if not (old_status == 'draft' and new_status == 'active'):
                        raise ValidationError(
                            _('Invalid status transition.')
                        )
                        
                # Check if proposal has votes when changing status
                if new_status in ['under_review', 'approved', 'rejected']:
                    if not self.instance.votes.exists():
                        raise ValidationError(
                            _('Proposal must have votes before changing to this status.')
                        )
                        
        return cleaned_data

class VoteForm(forms.ModelForm):
    """Form for submitting votes on proposals.
    
    This form handles:
    - Vote submission
    - Unique vote validation
    - Proposal status validation
    
    Attributes:
        proposal (ModelChoiceField): Proposal being voted on
        user (ModelChoiceField): User submitting vote
    """
    
    class Meta:
        model = Vote
        fields = ['proposal']
        widgets = {
            'proposal': forms.HiddenInput()
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize form with user and proposal."""
        self.user = kwargs.pop('user', None)
        self.proposal = kwargs.pop('proposal', None)
        super().__init__(*args, **kwargs)
        
        if self.proposal:
            self.fields['proposal'].initial = self.proposal
            
    def clean(self):
        """Validate vote submission.
        
        Returns:
            dict: Cleaned form data
            
        Raises:
            ValidationError: If validation fails
        """
        cleaned_data = super().clean()
        
        if not self.user or not self.user.is_authenticated:
            raise ValidationError(
                _('You must be logged in to vote.')
            )
            
        proposal = cleaned_data.get('proposal')
        if not proposal:
            raise ValidationError(
                _('Proposal is required.')
            )
            
        # Check if proposal is votable
        if not proposal.is_votable:
            raise ValidationError(
                _('This proposal is not currently accepting votes.')
            )
            
        # Check if user has already voted
        if Vote.objects.filter(
            proposal=proposal,
            user=self.user
        ).exists():
            raise ValidationError(
                _('You have already voted on this proposal.')
            )
            
        # Add user to cleaned data
        cleaned_data['user'] = self.user
        return cleaned_data
        
    def save(self, commit=True):
        """Save vote with user.
        
        Args:
            commit: Whether to save to database
            
        Returns:
            Vote: Created vote instance
        """
        vote = super().save(commit=False)
        vote.user = self.user
        
        if commit:
            vote.save()
            
        return vote 