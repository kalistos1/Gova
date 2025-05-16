"""Custom permissions for the reports app."""

from rest_framework import permissions
import logging
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

class IsVerifiedUser(permissions.BasePermission):
    """Permission to check if user is verified."""
    
    message = _('You must verify your identity to perform this action.')
    
    def has_permission(self, request, view):
        """Check if user is verified."""
        if not request.user.is_authenticated:
            return False
        return request.user.nin_verified or request.user.bvn_verified

class IsLGAOfficial(permissions.BasePermission):
    """Permission to check if user is an LGA official."""
    
    message = _('You must be an LGA official to perform this action.')
    
    def has_permission(self, request, view):
        """Check if user is an LGA official."""
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'is_lga_official') and request.user.is_lga_official
    
    def has_object_permission(self, request, view, obj):
        """Check if user is official for the report's LGA."""
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'is_lga_official') or not request.user.is_lga_official:
            return False
        return obj.lga == request.user.lga

class IsStateOfficial(permissions.BasePermission):
    """Permission to check if user is a state official."""
    
    message = _('You must be a state official to perform this action.')
    
    def has_permission(self, request, view):
        """Check if user is a state official."""
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'is_state_official') and request.user.is_state_official

class CanInitializePayment(permissions.BasePermission):
    """Permission to check if user can initialize payments."""
    
    message = _('You do not have permission to initialize payments.')
    
    def has_permission(self, request, view):
        """Check if user can initialize payments."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_initialize_payment')

class CanVerifyPayment(permissions.BasePermission):
    """Permission to check if user can verify payments."""
    
    message = _('You do not have permission to verify payments.')
    
    def has_permission(self, request, view):
        """Check if user can verify payments."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_verify_payment')

class CanTranscribeVoiceNote(permissions.BasePermission):
    """Permission to check if user can transcribe voice notes."""
    
    message = _('You do not have permission to transcribe voice notes.')
    
    def has_permission(self, request, view):
        """Check if user can transcribe voice notes."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_transcribe_voice_note')

class CanSendSMS(permissions.BasePermission):
    """Permission to check if user can send SMS messages."""
    
    message = _('You do not have permission to send SMS messages.')
    
    def has_permission(self, request, view):
        """Check if user can send SMS messages."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_send_sms')

class CanHandleUSSD(permissions.BasePermission):
    """Permission to check if user can handle USSD requests."""
    
    message = _('You do not have permission to handle USSD requests.')
    
    def has_permission(self, request, view):
        """Check if user can handle USSD requests."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_handle_ussd')

class CanAssignReports(permissions.BasePermission):
    """Permission to check if user can assign reports."""
    
    message = _('You do not have permission to assign reports.')
    
    def has_permission(self, request, view):
        """Check if user can assign reports."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_assign_reports')
    
    def has_object_permission(self, request, view, obj):
        """Check if user can assign this specific report."""
        if not request.user.is_authenticated:
            return False
        if not request.user.has_perm('reports.can_assign_reports'):
            return False
            
        # State officials can assign any report
        if hasattr(request.user, 'is_state_official') and request.user.is_state_official:
            return True
            
        # LGA officials can only assign reports in their LGA
        if hasattr(request.user, 'is_lga_official') and request.user.is_lga_official:
            return obj.lga == request.user.lga
            
        return False

class CanTranslateReports(permissions.BasePermission):
    """Permission to check if user can translate reports."""
    
    message = _('You do not have permission to translate reports.')
    
    def has_permission(self, request, view):
        """Check if user can translate reports."""
        if not request.user.is_authenticated:
            return False
        return request.user.has_perm('reports.can_translate_reports')

class CanViewStatistics(permissions.BasePermission):
    """Permission to check if user can view statistics."""
    
    message = _('You do not have permission to view statistics.')
    
    def has_permission(self, request, view):
        """Check if user can view statistics."""
        if not request.user.is_authenticated:
            return False
        return (
            request.user.is_staff or
            hasattr(request.user, 'is_state_official') and request.user.is_state_official or
            hasattr(request.user, 'is_lga_official') and request.user.is_lga_official
        )

class CanManageReports(permissions.BasePermission):
    """Permission to check if user can manage reports."""
    
    message = _('You do not have permission to manage reports.')
    
    def has_permission(self, request, view):
        """Check if user can manage reports."""
        if not request.user.is_authenticated:
            return False
            
        # Staff and officials can manage reports
        return (
            request.user.is_staff or
            hasattr(request.user, 'is_lga_official') or
            hasattr(request.user, 'is_state_official')
        )
        
    def has_object_permission(self, request, view, obj):
        """Check if user can manage specific report."""
        if not request.user.is_authenticated:
            return False
            
        # Staff can manage any report
        if request.user.is_staff:
            return True
            
        # Officials can only manage reports in their jurisdiction
        if hasattr(request.user, 'is_lga_official'):
            return obj.lga == request.user.lga
            
        if hasattr(request.user, 'is_state_official'):
            return True
            
        # Regular users can only manage their own reports
        return obj.reporter == request.user

class CanViewReportDetails(permissions.BasePermission):
    """Permission to check if user can view report details."""
    
    message = _('You do not have permission to view this report.')
    
    def has_object_permission(self, request, view, obj):
        """Check if user can view specific report."""
        # Anonymous reports are public
        if obj.is_anonymous:
            return True
            
        if not request.user.is_authenticated:
            return False
            
        # Staff and officials can view any report
        if request.user.is_staff:
            return True
            
        # Officials can view reports in their jurisdiction
        if hasattr(request.user, 'is_lga_official'):
            return obj.lga == request.user.lga
            
        if hasattr(request.user, 'is_state_official'):
            return True
            
        # Users can view their own reports
        return obj.reporter == request.user 