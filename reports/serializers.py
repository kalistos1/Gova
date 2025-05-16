from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Report, ReportComment, AuditLog
from core.models import Landmark, Location
from accounts.models import User  # Assuming User model is in users app
# from django.contrib.gis.geos import Point
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data in reports."""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone')


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location model with camelCase field names."""
    
    locationId = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = Location
        fields = ['locationId', 'name', 'latitude', 'longitude']


class LandmarkSerializer(serializers.ModelSerializer):
    """Serializer for Landmark model with camelCase field names."""
    
    landmarkId = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = Landmark
        fields = ['landmarkId', 'name', 'description']


class ReportCommentSerializer(serializers.ModelSerializer):
    """Serializer for report comments."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ReportComment
        fields = (
            'id', 'report', 'user', 'content',
            'created_at', 'updated_at', 'is_official'
        )
        read_only_fields = ('id', 'report', 'user', 'created_at', 'updated_at')


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = (
            'id', 'report', 'user', 'action',
            'old_value', 'new_value', 'created_at'
        )
        read_only_fields = ('id', 'report', 'user', 'created_at')


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for retrieving reports."""
    
    reporter = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    comments = ReportCommentSerializer(many=True, read_only=True)
    audit_logs = AuditLogSerializer(many=True, read_only=True)
    location = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'category',
            'priority', 'status', 'location', 'address',
            'lga', 'landmark', 'images', 'videos',
            'voice_notes', 'reporter', 'created_at',
            'updated_at', 'is_anonymous', 'upvotes',
            'ai_summary', 'ai_priority_score', 'assigned_to',
            'assigned_at', 'resolved_at', 'submission_channel',
            'submission_language', 'original_text',
            'device_info', 'offline_sync_id', 'payment_status',
            'payment_amount', 'transaction_reference',
            'transaction_id', 'payment_date', 'nin_verified',
            'nin_verification_date', 'comments', 'audit_logs'
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'upvotes',
            'ai_summary', 'ai_priority_score', 'assigned_at',
            'resolved_at', 'payment_date', 'nin_verification_date'
        )
    
    def get_location(self, obj):
        """Convert Point object to lat/lon dict."""
        if obj.location:
            return {
                'latitude': obj.location.y,
                'longitude': obj.location.x
            }
        return None


class ReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reports."""
    
    latitude = serializers.FloatField(required=False, write_only=True)
    longitude = serializers.FloatField(required=False, write_only=True)
    
    class Meta:
        model = Report
        fields = (
            'title', 'description', 'category', 'priority',
            'address', 'lga', 'landmark', 'is_anonymous',
            'submission_channel', 'submission_language',
            'device_info', 'offline_sync_id', 'latitude',
            'longitude'
        )
    
    def validate(self, data):
        """Validate report data."""
        # Handle location
        latitude = data.pop('latitude', None)
        longitude = data.pop('longitude', None)
        
        if latitude is not None and longitude is not None:
            data['location'] = Point(longitude, latitude)
        
        # Validate title length
        if len(data['title']) < 10:
            raise serializers.ValidationError({
                'title': _('Title must be at least 10 characters long')
            })
        
        # Validate description length
        if len(data['description']) < 50:
            raise serializers.ValidationError({
                'description': _('Description must be at least 50 characters long')
            })
        
        return data


class ReportUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating reports."""
    
    class Meta:
        model = Report
        fields = ('status', 'priority', 'assigned_to')


class ReportAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning reports to officials."""
    
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True
        ).filter(
            Q(is_lga_official=True) | Q(is_state_official=True)
        )
    )


class ReportTranslationSerializer(serializers.Serializer):
    """Serializer for translating report content."""
    
    target_language = serializers.ChoiceField(
        choices=['en', 'ig', 'pcm'],
        help_text=_('Language to translate to (en=English, ig=Igbo, pcm=Pidgin)')
    )


class NINVerificationSerializer(serializers.Serializer):
    """Serializer for NIN verification."""
    
    nin = serializers.CharField(
        max_length=11,
        min_length=11,
        help_text=_('11-digit NIN number')
    )


class BVNVerificationSerializer(serializers.Serializer):
    """Serializer for BVN verification."""
    
    bvn = serializers.CharField(
        max_length=11,
        min_length=11,
        help_text=_('11-digit BVN number')
    )


class PaymentInitializationSerializer(serializers.Serializer):
    """Serializer for initializing payments."""
    
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Amount to pay in Naira')
    )
    email = serializers.EmailField(
        help_text=_('Email address for payment notification')
    )
    phone = serializers.CharField(
        required=False,
        help_text=_('Phone number for payment notification')
    )
    name = serializers.CharField(
        required=False,
        help_text=_('Full name for payment')
    )


class USSDRequestSerializer(serializers.Serializer):
    """Serializer for USSD requests."""
    
    session_id = serializers.CharField(
        help_text=_('USSD session ID')
    )
    phone_number = serializers.CharField(
        help_text=_('User\'s phone number')
    )
    text = serializers.CharField(
        help_text=_('USSD input text'),
        allow_blank=True
    )


class SMSRequestSerializer(serializers.Serializer):
    """Serializer for SMS requests."""
    
    to = serializers.CharField(
        help_text=_('Recipient phone number')
    )
    message = serializers.CharField(
        help_text=_('Message content')
    )


class VoiceTranscriptionSerializer(serializers.Serializer):
    """Serializer for voice note transcription."""
    
    voice_note_url = serializers.URLField(
        help_text=_('URL of the voice note to transcribe')
    )
    source_language = serializers.ChoiceField(
        choices=['en', 'ig', 'pcm'],
        default='en',
        help_text=_('Source language (en=English, ig=Igbo, pcm=Pidgin)')
    )


class ReportStatisticsSerializer(serializers.Serializer):
    """Serializer for report statistics."""
    
    total_reports = serializers.IntegerField()
    reports_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )
    reports_by_category = serializers.DictField(
        child=serializers.IntegerField()
    )
    reports_by_priority = serializers.DictField(
        child=serializers.IntegerField()
    )
    average_resolution_time = serializers.DurationField()
    reports_over_time = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        )
    )