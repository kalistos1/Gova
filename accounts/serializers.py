from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from typing import Dict, Any
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User

from core.models import Location, Reward, Kiosk, Synclog
from django.db.models import Sum

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with camelCase fields."""
    
    userId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='date_joined', read_only=True)
    updatedAt = serializers.DateTimeField(source='last_login', read_only=True)
    fullName = serializers.SerializerMethodField()
    isStateOfficial = serializers.BooleanField(source='is_state_official', read_only=True)
    isLgaOfficial = serializers.BooleanField(source='is_lga_official', read_only=True)
    phoneNumber = serializers.CharField(source='phone_number', read_only=True)
    department = serializers.CharField(read_only=True)
    position = serializers.CharField(read_only=True)
    isEmailVerified = serializers.BooleanField(source='is_email_verified')
    
    class Meta:
        model = User
        fields = [
            'userId', 'email', 'fullName', 'firstName', 'lastName',
            'isStateOfficial', 'isLgaOfficial', 'phoneNumber',
            'department', 'position', 'createdAt', 'updatedAt', 'isEmailVerified'
        ]
        read_only_fields = [
            'userId', 'email', 'isStateOfficial', 'isLgaOfficial',
            'createdAt', 'updatedAt'
        ]
    
    def get_full_name(self, obj: User) -> str:
        """Get user's full name.
        
        Args:
            obj: User instance.
            
        Returns:
            str: User's full name or email if name not set.
        """
        return obj.get_full_name() or obj.email

class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        help_text=_('Password must be at least 8 characters long')
    )
    confirmPassword = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('Confirm your password')
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'confirmPassword',
            'firstName', 'lastName', 'phoneNumber',
            'department', 'position'
        ]
        extra_kwargs = {
            'firstName': {'source': 'first_name', 'required': True},
            'lastName': {'source': 'last_name', 'required': True},
            'phoneNumber': {'source': 'phone_number', 'required': True},
            'department': {'required': False},
            'position': {'required': False}
        }
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user creation data.
        
        Args:
            data: Dictionary containing user data.
            
        Returns:
            Dict containing validated data.
            
        Raises:
            ValidationError: If passwords don't match or email is invalid.
        """
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError({
                'confirmPassword': _('Passwords do not match')
            })
        
        # Check if email is already registered
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({
                'email': _('A user with this email already exists')
            })
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> User:
        """Create a new user.
        
        Args:
            validated_data: Dictionary containing validated user data.
            
        Returns:
            User: Newly created user instance.
        """
        # Remove confirm_password from data
        validated_data.pop('confirmPassword', None)
        
        # Create user with encrypted password
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number'],
            department=validated_data.get('department', ''),
            position=validated_data.get('position', '')
        )
        
        return user

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    
    class Meta:
        model = User
        fields = [
            'firstName', 'lastName', 'phoneNumber',
            'department', 'position'
        ]
        extra_kwargs = {
            'firstName': {'source': 'first_name'},
            'lastName': {'source': 'last_name'},
            'phoneNumber': {'source': 'phone_number'}
        }
    
    def validate_phone_number(self, value: str) -> str:
        """Validate phone number format.
        
        Args:
            value: Phone number to validate.
            
        Returns:
            str: Validated phone number.
            
        Raises:
            ValidationError: If phone number format is invalid.
        """
        if not value.startswith('+234') and not value.startswith('0'):
            raise serializers.ValidationError(
                _('Phone number must start with +234 or 0')
            )
        return value

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration with password validation."""
    
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirmPassword = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    firstName = serializers.CharField(source='first_name', required=True)
    lastName = serializers.CharField(source='last_name', required=True)
    phoneNumber = serializers.CharField(source='phone_number', required=False)
    isStateOfficial = serializers.BooleanField(source='is_state_official', required=False, default=False)
    isLgaOfficial = serializers.BooleanField(source='is_lga_official', required=False, default=False)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'confirmPassword', 'firstName', 'lastName',
            'phoneNumber', 'department', 'position', 'isStateOfficial',
            'isLgaOfficial'
        ]
    
    def validate(self, data):
        """Validate registration data."""
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError({
                'confirmPassword': _('Passwords do not match.')
            })
        
        # Validate password strength
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({
                'password': list(e.messages)
            })
        
        # Validate official status
        if data.get('is_state_official') and data.get('is_lga_official'):
            raise serializers.ValidationError({
                'isStateOfficial': _('User cannot be both state and LGA official.')
            })
        
        return data
    
    def create(self, validated_data):
        """Create a new user with validated data."""
        validated_data.pop('confirmPassword')
        user = User.objects.create_user(**validated_data)
        return user

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    
    firstName = serializers.CharField(source='first_name', required=False)
    lastName = serializers.CharField(source='last_name', required=False)
    phoneNumber = serializers.CharField(source='phone_number', required=False)
    
    class Meta:
        model = User
        fields = [
            'firstName', 'lastName', 'phoneNumber',
            'department', 'position'
        ]

class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password."""
    
    currentPassword = serializers.CharField(required=True, style={'input_type': 'password'})
    newPassword = serializers.CharField(required=True, style={'input_type': 'password'})
    confirmPassword = serializers.CharField(required=True, style={'input_type': 'password'})
    
    def validate(self, data):
        """Validate password change data."""
        user = self.context['request'].user
        
        # Check current password
        if not user.check_password(data['currentPassword']):
            raise serializers.ValidationError({
                'currentPassword': _('Current password is incorrect.')
            })
        
        # Check if new passwords match
        if data['newPassword'] != data['confirmPassword']:
            raise serializers.ValidationError({
                'confirmPassword': _('New passwords do not match.')
            })
        
        # Check if new password is same as current
        if data['currentPassword'] == data['newPassword']:
            raise serializers.ValidationError({
                'newPassword': _('New password must be different from current password.')
            })
        
        # Validate password strength
        try:
            validate_password(data['newPassword'])
        except ValidationError as e:
            raise serializers.ValidationError({
                'newPassword': list(e.messages)
            })
        
        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset."""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Validate email format."""
        if not User.objects.filter(email=value, is_active=True).exists():
            # Don't raise error (security best practice)
            pass
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset."""
    
    token = serializers.CharField(required=True)
    newPassword = serializers.CharField(required=True, style={'input_type': 'password'})
    confirmPassword = serializers.CharField(required=True, style={'input_type': 'password'})
    
    def validate(self, data):
        """Validate password reset data."""
        if data['newPassword'] != data['confirmPassword']:
            raise serializers.ValidationError({
                'confirmPassword': _('Passwords do not match.')
            })
        
        # Validate password strength
        try:
            validate_password(data['newPassword'])
        except ValidationError as e:
            raise serializers.ValidationError({
                'newPassword': list(e.messages)
            })
        
        return data

class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification."""
    
    token = serializers.CharField(required=True)

class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resending verification email."""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Validate email format and verification status."""
        try:
            user = User.objects.get(email=value, is_active=True)
            if user.is_email_verified:
                raise serializers.ValidationError(
                    _('Email is already verified.')
                )
        except User.DoesNotExist:
            # Don't raise error (security best practice)
            pass
        return value

class NINVerificationSerializer(serializers.Serializer):
    """Serializer for NIN verification request."""
    
    nin = serializers.CharField(
        required=True,
        min_length=11,
        max_length=11,
        help_text=_('11-digit NIN number')
    )
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    date_of_birth = serializers.DateField(required=True)

class RewardSerializer(serializers.ModelSerializer):
    """Serializer for user rewards with camelCase fields."""
    
    rewardId = serializers.UUIDField(source='id', read_only=True)
    userId = serializers.UUIDField(source='user.id', read_only=True)
    rewardType = serializers.CharField(source='reward_type')
    rewardAmount = serializers.DecimalField(
        source='reward_amount',
        max_digits=10,
        decimal_places=2
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', read_only=True)
    isRedeemed = serializers.BooleanField(source='is_redeemed', read_only=True)
    
    class Meta:
        model = Reward
        fields = [
            'rewardId', 'userId', 'rewardType', 'rewardAmount',
            'description', 'createdAt', 'expiresAt', 'isRedeemed'
        ]

class KioskSerializer(serializers.ModelSerializer):
    """Serializer for kiosks with camelCase fields."""
    
    kioskId = serializers.UUIDField(source='id', read_only=True)
    locationId = serializers.UUIDField(source='location.id', read_only=True)
    locationName = serializers.CharField(source='location.name', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    lastSyncAt = serializers.DateTimeField(source='last_sync_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = Kiosk
        fields = [
            'kioskId', 'locationId', 'locationName', 'name',
            'isActive', 'lastSyncAt', 'createdAt'
        ]
        

# class SyncLogSerializer(serializers.ModelSerializer):
#     """Serializer for kiosk sync logs with camelCase fields."""
    
#     syncId = serializers.UUIDField(source='id', read_only=True)
#     kioskId = serializers.UUIDField(source='kiosk.id', read_only=True)
#     kioskName = serializers.CharField(source='kiosk.name', read_only=True)
#     syncType = serializers.CharField(source='sync_type')
#     syncStatus = serializers.CharField(source='sync_status')
#     syncStartedAt = serializers.DateTimeField(source='sync_started_at')
#     syncCompletedAt = serializers.DateTimeField(source='sync_completed_at', read_only=True)
#     errorMessage = serializers.CharField(source='error_message', required=False)
    
#     class Meta:
#         model = SyncLog
#         fields = [
#             'syncId', 'kioskId', 'kioskName', 'syncType',
#             'syncStatus', 'syncStartedAt', 'syncCompletedAt',
#             'errorMessage', 'details'
#         ]
#         read_only_fields = ['syncCompletedAt']
    
#     def validate_sync_type(self, value):
#         """Validate sync type."""
#         valid_types = ['full', 'incremental', 'emergency']
#         if value not in valid_types:
#             raise serializers.ValidationError(
#                 _('Invalid sync type. Must be one of: {}').format(', '.join(valid_types))
#             )
#         return value
    
#     def validate_sync_status(self, value):
#         """Validate sync status."""
#         valid_statuses = ['pending', 'in_progress', 'completed', 'failed']
#         if value not in valid_statuses:
#             raise serializers.ValidationError(
#                 _('Invalid sync status. Must be one of: {}').format(', '.join(valid_statuses))
#             )
#         return value

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile with camelCase fields."""
    
    userId = serializers.UUIDField(source='id', read_only=True)
    locationId = serializers.UUIDField(source='location.id', read_only=True)
    locationName = serializers.CharField(source='location.name', read_only=True)
    isStateOfficial = serializers.BooleanField(source='is_state_official', read_only=True)
    isLgaOfficial = serializers.BooleanField(source='is_lga_official', read_only=True)
    isKioskOperator = serializers.BooleanField(source='is_kiosk_operator', read_only=True)
    phoneNumber = serializers.CharField(source='phone_number', read_only=True)
    dateJoined = serializers.DateTimeField(source='date_joined', read_only=True)
    lastLogin = serializers.DateTimeField(source='last_login', read_only=True)
    totalRewards = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'userId', 'email', 'firstName', 'lastName', 'phoneNumber',
            'locationId', 'locationName', 'isStateOfficial', 'isLgaOfficial',
            'isKioskOperator', 'department', 'position', 'dateJoined',
            'lastLogin', 'totalRewards'
        ]
    
    def get_total_rewards(self, obj):
        """Calculate total rewards for user."""
        return obj.rewards.filter(is_redeemed=False).aggregate(
            total=Sum('reward_amount')
        )['total'] or 0 