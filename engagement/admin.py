from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Message, Notification, RecipientGroup

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin configuration for Message model."""
    
    list_display = [
        'id', 'get_sender', 'get_query_preview', 'get_location',
        'is_read', 'is_anonymous', 'created_at'
    ]
    list_filter = ['is_read', 'is_anonymous', 'created_at']
    search_fields = ['query', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'parent', 'location', 'landmark']
    
    def get_sender(self, obj):
        """Get formatted sender name."""
        if obj.user:
            return f'{obj.user.get_full_name()} ({obj.user.username})'
        return _('Anonymous')
    get_sender.short_description = _('Sender')
    
    def get_query_preview(self, obj):
        """Get preview of message query."""
        return obj.query[:50] + '...' if len(obj.query) > 50 else obj.query
    get_query_preview.short_description = _('Message')
    
    def get_location(self, obj):
        """Get formatted location."""
        if obj.location:
            return obj.location.name
        if obj.landmark:
            return f'{obj.landmark.name} ({obj.landmark.location.name})'
        return '-'
    get_location.short_description = _('Location')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification model."""
    
    list_display = [
        'id', 'title', 'get_sender', 'target_type', 'priority',
        'is_read', 'created_at'
    ]
    list_filter = ['target_type', 'priority', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'sender__username', 'sender__email']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['sender']
    
    def get_sender(self, obj):
        """Get formatted sender name."""
        return f'{obj.sender.get_full_name()} ({obj.sender.username})'
    get_sender.short_description = _('Sender')

@admin.register(RecipientGroup)
class RecipientGroupAdmin(admin.ModelAdmin):
    """Admin configuration for RecipientGroup model."""
    
    list_display = [
        'id', 'name', 'get_member_count', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'members__username', 'members__email']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['members']
    
    def get_member_count(self, obj):
        """Get formatted member count."""
        return obj.member_count
    get_member_count.short_description = _('Members')
