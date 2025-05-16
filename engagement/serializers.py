from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Message, Notification, RecipientGroup, Translation
from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with camelCase field names."""
    
    userId = serializers.UUIDField(source='id', read_only=True)
    fullName = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['userId', 'username', 'fullName', 'email']

    def get_fullName(self, obj):
        """Get full name of the user."""
        return obj.get_full_name() or obj.username


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model with camelCase field names."""
    
    messageId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    isAnonymous = serializers.BooleanField(source='is_anonymous', read_only=True)
    hasReplies = serializers.BooleanField(source='has_replies', read_only=True)
    user = UserSerializer(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), required=False)

    class Meta:
        model = Message
        fields = [
            'messageId', 'user', 'parent', 'query', 'location', 'landmark',
            'isRead', 'isAnonymous', 'hasReplies', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['messageId', 'isRead', 'isAnonymous', 'hasReplies', 'createdAt', 'updatedAt']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model with camelCase field names."""
    
    notificationId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    sender = UserSerializer(read_only=True)
    targetGroup = serializers.PrimaryKeyRelatedField(queryset=RecipientGroup.objects.all(), required=False)

    class Meta:
        model = Notification
        fields = [
            'notificationId', 'sender', 'title', 'message', 'targetGroup',
            'priority', 'isRead', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['notificationId', 'isRead', 'createdAt', 'updatedAt']


class RecipientGroupSerializer(serializers.ModelSerializer):
    """Serializer for RecipientGroup model with camelCase field names."""
    
    groupId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = RecipientGroup
        fields = [
            'groupId', 'name', 'description', 'isActive', 'members',
            'createdAt', 'updatedAt'
        ]
        read_only_fields = ['groupId', 'createdAt', 'updatedAt']


class TranslationSerializer(serializers.ModelSerializer):
    """Serializer for Translation model with camelCase field names."""
    
    translationId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Translation
        fields = [
            'translationId', 'sourceText', 'translatedText', 'sourceLanguage',
            'targetLanguage', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['translationId', 'createdAt', 'updatedAt']
        
        
class MessageCreateSerializer(serializers.ModelSerializer): 
    """Serializer for creating a Message with camelCase field names."""
    
    userId = serializers.UUIDField(source='user.id', required=False)
    parentId = serializers.UUIDField(source='parent.id', required=False)

    class Meta:
        model = Message
        fields = [
            'userId', 'parentId', 'query', 'location', 'landmark'
        ]
        read_only_fields = ['userId', 'parentId']
        
class MessageResponseSerializer(serializers.ModelSerializer): 
    """Serializer for creating a Message with camelCase field names."""
    
    userId = serializers.UUIDField(source='user.id', required=False)
    parentId = serializers.UUIDField(source='parent.id', required=False)

    class Meta:
        model = Message
        fields = [
            'userId', 'parentId', 'query', 'location', 'landmark'
        ]
        read_only_fields = ['userId', 'parentId']       
