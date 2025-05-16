from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import BaseModel, Location, Landmark

class Message(BaseModel):
    """Model for messages between citizens and officials.
    
    This model represents messages that can be sent by citizens (anonymous or
    authenticated) and responded to by state officials. Messages can be text
    or transcribed from voice recordings.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_messages',
        verbose_name=_('sender'),
        help_text=_('User who sent the message (optional for anonymous messages)')
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_('parent message'),
        help_text=_('Parent message if this is a response')
    )
    query = models.TextField(
        _('message'),
        help_text=_('Message content (text or transcribed from voice)')
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        verbose_name=_('location'),
        help_text=_('Location related to the message')
    )
    landmark = models.ForeignKey(
        Landmark,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        verbose_name=_('landmark'),
        help_text=_('Landmark related to the message')
    )
    is_read = models.BooleanField(
        _('read status'),
        default=False,
        help_text=_('Whether the message has been read')
    )
    is_anonymous = models.BooleanField(
        _('anonymous status'),
        default=False,
        help_text=_('Whether the message was sent anonymously')
    )
    transcription_confidence = models.FloatField(
        _('transcription confidence'),
        null=True,
        blank=True,
        help_text=_('Confidence score for voice transcription (0.0 to 1.0)')
    )
    content_type = models.CharField(
        _('content type'),
        max_length=20,
        choices=[
            ('text', _('Text')),
            ('voice', _('Voice')),
        ],
        default='text',
        help_text=_('Type of message content')
    )
    
    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['parent', 'created_at']),
            models.Index(fields=['is_read']),
            models.Index(fields=['is_anonymous']),
            models.Index(fields=['content_type']),
        ]
        
    def __str__(self):
        """Return string representation of the message."""
        sender = self.user.get_full_name() if self.user else _('Anonymous')
        return f'{sender}: {self.query[:50]}...'
        
    @property
    def has_replies(self) -> bool:
        """Check if the message has any replies.
        
        Returns:
            bool: True if message has replies, False otherwise.
        """
        return self.replies.exists()
        
    def mark_as_read(self, save: bool = True) -> None:
        """Mark the message as read.
        
        Args:
            save: Whether to save the model after updating.
        """
        self.is_read = True
        if save:
            self.save(update_fields=['is_read'])

class Notification(BaseModel):
    """Model for system notifications.
    
    This model represents notifications that can be sent to users or groups
    by administrators. Notifications can have different priority levels and
    target types.
    """
    
    class Priority(models.TextChoices):
        """Notification priority levels."""
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
    
    class TargetType(models.TextChoices):
        """Notification target types."""
        USER = 'user', _('User')
        GROUP = 'group', _('Group')
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_notifications',
        verbose_name=_('sender'),
        help_text=_('User who sent the notification')
    )
    title = models.CharField(
        _('title'),
        max_length=200,
        help_text=_('Notification title')
    )
    message = models.TextField(
        _('message'),
        help_text=_('Notification content')
    )
    target_type = models.CharField(
        _('target type'),
        max_length=10,
        choices=TargetType.choices,
        help_text=_('Type of notification target (user or group)')
    )
    target_id = models.UUIDField(
        _('target id'),
        help_text=_('ID of the target user or group')
    )
    priority = models.CharField(
        _('priority'),
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        help_text=_('Notification priority level')
    )
    is_read = models.BooleanField(
        _('read status'),
        default=False,
        help_text=_('Whether the notification has been read')
    )
    
    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_read']),
        ]
        
    def __str__(self):
        """Return string representation of the notification."""
        return f'{self.title} ({self.get_priority_display()})'
        
    def mark_as_read(self, save: bool = True) -> None:
        """Mark the notification as read.
        
        Args:
            save: Whether to save the model after updating.
        """
        self.is_read = True
        if save:
            self.save(update_fields=['is_read'])

class RecipientGroup(BaseModel):
    """Model for notification recipient groups.
    
    This model represents groups of users that can be targeted for
    notifications. Groups can be used to send notifications to specific
    categories of users (e.g., all state officials, all citizens in a
    particular LGA).
    """
    
    name = models.CharField(
        _('name'),
        max_length=100,
        help_text=_('Name of the recipient group')
    )
    description = models.TextField(
        _('description'),
        help_text=_('Description of the group and its purpose')
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='recipient_groups',
        verbose_name=_('members'),
        help_text=_('Users who belong to this group')
    )
    is_active = models.BooleanField(
        _('active status'),
        default=True,
        help_text=_('Whether the group is currently active')
    )
    
    class Meta:
        verbose_name = _('recipient group')
        verbose_name_plural = _('recipient groups')
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
        
    def __str__(self):
        """Return string representation of the recipient group."""
        return self.name
        
    @property
    def member_count(self) -> int:
        """Get the number of members in the group.
        
        Returns:
            int: Number of members.
        """
        return self.members.count()
        
    def add_member(self, user) -> None:
        """Add a user to the group.
        
        Args:
            user: User to add to the group.
        """
        self.members.add(user)
        
    def remove_member(self, user) -> None:
        """Remove a user from the group.
        
        Args:
            user: User to remove from the group.
        """
        self.members.remove(user)
        
class Translation(BaseModel):
    """Model for storing translations of messages.
    
    This model represents translations of messages in different languages.
    Translations can be used to provide multilingual support for the
    application.
    """   
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_('message'),
        help_text=_('Message being translated')
    )
    language_code = models.CharField(
        _('language code'),
        max_length=10,
        help_text=_('Language code for the translation (e.g., "en", "fr")')
    )
    translated_text = models.TextField(
        _('translated text'),
        help_text=_('Translated content of the message')
    )
    
    class Meta:
        verbose_name = _('translation')
        verbose_name_plural = _('translations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message', 'language_code']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        """Return string representation of the translation."""
        return f'Translation of {self.message} in {self.language_code}'     
    
    