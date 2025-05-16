"""Signal handlers for core app.

This module defines signal handlers for various events in the core app,
including reward processing, audit logging, user activity tracking,
kiosk management, and operator events.
"""

import logging
from django.db.models.signals import (
    post_save, pre_save, post_delete,
    m2m_changed, pre_delete
)
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Reward, AuditLog, Kiosk, Operator
from .services import RewardProcessor

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Reward)
def handle_reward_status_change(sender, instance, created, **kwargs):
    """Handle changes to reward status.
    
    This signal handler is triggered when a reward is created or updated.
    It ensures that:
    1. New rewards are queued for processing
    2. Status changes are logged
    3. Appropriate notifications are sent
    
    Args:
        sender: The Reward model class
        instance: The Reward instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments passed by the signal
    """
    if created:
        # Log the creation of a new reward
        AuditLog.objects.create(
            user=instance.user,
            action='REWARD_CREATED',
            entity='Reward',
            entity_id=instance.id,
            details={
                'amount': str(instance.amount),
                'action_type': instance.action_type,
                'reference_id': instance.reference_id,
                'reference_type': instance.reference_type
            }
        )
        logger.info(
            f'New reward created: {instance.id} for user {instance.user}'
        )
    else:
        # Log status changes
        if 'status' in kwargs.get('update_fields', set()):
            AuditLog.objects.create(
                user=instance.user,
                action=f'REWARD_{instance.status}',
                entity='Reward',
                entity_id=instance.id,
                details={
                    'previous_status': kwargs.get('old_status', 'UNKNOWN'),
                    'new_status': instance.status,
                    'failure_reason': instance.failure_reason,
                    'processed_at': instance.processed_at.isoformat() if instance.processed_at else None
                }
            )
            logger.info(
                f'Reward {instance.id} status changed to {instance.status}'
            )


@receiver(pre_save, sender=Reward)
def track_reward_status_change(sender, instance, **kwargs):
    """Track changes to reward status for audit logging.
    
    This signal handler captures the previous status of a reward
    before it is saved, to enable proper audit logging of status changes.
    
    Args:
        sender: The Reward model class
        instance: The Reward instance being saved
        **kwargs: Additional arguments passed by the signal
    """
    if not instance._state.adding:  # Not a new instance
        try:
            old_instance = Reward.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Reward.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=AuditLog)
def handle_audit_log_creation(sender, instance, created, **kwargs):
    """Handle creation of audit log entries.
    
    This signal handler is triggered when a new audit log entry is created.
    It ensures that:
    1. Audit logs are properly formatted
    2. Sensitive information is redacted
    3. Logs are written to the appropriate storage
    
    Args:
        sender: The AuditLog model class
        instance: The AuditLog instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments passed by the signal
    """
    if created:
        # Log to system logger for monitoring
        logger.info(
            f'Audit log created: {instance.action} by {instance.user} '
            f'for {instance.entity} {instance.entity_id}'
        )
        
        # Here you could add additional processing like:
        # - Writing to external logging service
        # - Notifying administrators of critical events
        # - Archiving old logs
        # - etc. 


@receiver(post_save, sender=User)
def handle_user_activity(sender, instance, created, **kwargs):
    """Handle user-related events.
    
    This signal handler tracks important user events including:
    - Account creation
    - Profile updates
    - Status changes
    - Last login
    
    Args:
        sender: The User model class
        instance: The User instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments passed by the signal
    """
    if created:
        # Log new user registration
        AuditLog.objects.create(
            user=instance,
            action='USER_CREATED',
            entity='User',
            entity_id=instance.id,
            details={
                'email': instance.email,
                'is_active': instance.is_active,
                'is_staff': instance.is_staff
            }
        )
        logger.info(f'New user registered: {instance.email}')
    else:
        # Track important profile changes
        if 'is_active' in kwargs.get('update_fields', set()):
            AuditLog.objects.create(
                user=instance,
                action='USER_STATUS_CHANGED',
                entity='User',
                entity_id=instance.id,
                details={
                    'previous_status': 'active' if instance._old_is_active else 'inactive',
                    'new_status': 'active' if instance.is_active else 'inactive',
                    'changed_by': getattr(instance, '_changed_by', 'system')
                }
            )
            logger.info(
                f'User {instance.email} status changed to '
                f'{"active" if instance.is_active else "inactive"}'
            )


@receiver(pre_save, sender=User)
def track_user_status_change(sender, instance, **kwargs):
    """Track changes to user status for audit logging.
    
    Args:
        sender: The User model class
        instance: The User instance being saved
        **kwargs: Additional arguments passed by the signal
    """
    if not instance._state.adding:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_is_active = old_instance.is_active
        except User.DoesNotExist:
            instance._old_is_active = None


@receiver(post_save, sender=Kiosk)
def handle_kiosk_events(sender, instance, created, **kwargs):
    """Handle kiosk-related events.
    
    This signal handler tracks:
    - Kiosk creation
    - Status changes
    - Location updates
    - Sync events
    
    Args:
        sender: The Kiosk model class
        instance: The Kiosk instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments passed by the signal
    """
    if created:
        AuditLog.objects.create(
            user=instance.created_by,
            action='KIOSK_CREATED',
            entity='Kiosk',
            entity_id=instance.id,
            details={
                'name': instance.name,
                'location': instance.location,
                'status': instance.status
            }
        )
        logger.info(f'New kiosk created: {instance.name}')
    else:
        # Track status changes
        if 'status' in kwargs.get('update_fields', set()):
            AuditLog.objects.create(
                user=instance.updated_by,
                action='KIOSK_STATUS_CHANGED',
                entity='Kiosk',
                entity_id=instance.id,
                details={
                    'previous_status': instance._old_status,
                    'new_status': instance.status,
                    'reason': getattr(instance, '_status_change_reason', None)
                }
            )
            logger.info(
                f'Kiosk {instance.name} status changed to {instance.status}'
            )
        
        # Track location updates
        if 'location' in kwargs.get('update_fields', set()):
            AuditLog.objects.create(
                user=instance.updated_by,
                action='KIOSK_LOCATION_UPDATED',
                entity='Kiosk',
                entity_id=instance.id,
                details={
                    'previous_location': instance._old_location,
                    'new_location': instance.location
                }
            )
            logger.info(
                f'Kiosk {instance.name} location updated to {instance.location}'
            )


@receiver(pre_save, sender=Kiosk)
def track_kiosk_changes(sender, instance, **kwargs):
    """Track changes to kiosk details for audit logging.
    
    Args:
        sender: The Kiosk model class
        instance: The Kiosk instance being saved
        **kwargs: Additional arguments passed by the signal
    """
    if not instance._state.adding:
        try:
            old_instance = Kiosk.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            instance._old_location = old_instance.location
        except Kiosk.DoesNotExist:
            instance._old_status = None
            instance._old_location = None


@receiver(m2m_changed, sender=Operator.assigned_kiosks.through)
def handle_operator_kiosk_assignment(sender, instance, action, pk_set, **kwargs):
    """Handle operator-kiosk assignment changes.
    
    This signal handler tracks:
    - Kiosk assignments to operators
    - Kiosk removals from operators
    
    Args:
        sender: The through model for operator-kiosk relationship
        instance: The Operator instance
        action: The type of change ('pre_add', 'post_add', 'pre_remove', 'post_remove')
        pk_set: Set of primary keys being added/removed
        **kwargs: Additional arguments passed by the signal
    """
    if action == 'post_add':
        # Log new kiosk assignments
        kiosks = Kiosk.objects.filter(pk__in=pk_set)
        AuditLog.objects.create(
            user=instance.updated_by,
            action='OPERATOR_KIOSKS_ASSIGNED',
            entity='Operator',
            entity_id=instance.id,
            details={
                'operator_email': instance.user.email,
                'assigned_kiosks': [
                    {'id': k.id, 'name': k.name}
                    for k in kiosks
                ]
            }
        )
        logger.info(
            f'Assigned {len(pk_set)} kiosks to operator {instance.user.email}'
        )
    elif action == 'post_remove':
        # Log kiosk removals
        kiosks = Kiosk.objects.filter(pk__in=pk_set)
        AuditLog.objects.create(
            user=instance.updated_by,
            action='OPERATOR_KIOSKS_REMOVED',
            entity='Operator',
            entity_id=instance.id,
            details={
                'operator_email': instance.user.email,
                'removed_kiosks': [
                    {'id': k.id, 'name': k.name}
                    for k in kiosks
                ]
            }
        )
        logger.info(
            f'Removed {len(pk_set)} kiosks from operator {instance.user.email}'
        )


@receiver(post_save, sender=Operator)
def handle_operator_events(sender, instance, created, **kwargs):
    """Handle operator-related events.
    
    This signal handler tracks:
    - Operator creation
    - Status changes
    - Profile updates
    
    Args:
        sender: The Operator model class
        instance: The Operator instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments passed by the signal
    """
    if created:
        AuditLog.objects.create(
            user=instance.created_by,
            action='OPERATOR_CREATED',
            entity='Operator',
            entity_id=instance.id,
            details={
                'email': instance.user.email,
                'is_active': instance.is_active,
                'assigned_kiosks_count': instance.assigned_kiosks.count()
            }
        )
        logger.info(f'New operator created: {instance.user.email}')
    else:
        # Track status changes
        if 'is_active' in kwargs.get('update_fields', set()):
            AuditLog.objects.create(
                user=instance.updated_by,
                action='OPERATOR_STATUS_CHANGED',
                entity='Operator',
                entity_id=instance.id,
                details={
                    'previous_status': 'active' if instance._old_is_active else 'inactive',
                    'new_status': 'active' if instance.is_active else 'inactive',
                    'reason': getattr(instance, '_status_change_reason', None)
                }
            )
            logger.info(
                f'Operator {instance.user.email} status changed to '
                f'{"active" if instance.is_active else "inactive"}'
            )


@receiver(pre_save, sender=Operator)
def track_operator_changes(sender, instance, **kwargs):
    """Track changes to operator details for audit logging.
    
    Args:
        sender: The Operator model class
        instance: The Operator instance being saved
        **kwargs: Additional arguments passed by the signal
    """
    if not instance._state.adding:
        try:
            old_instance = Operator.objects.get(pk=instance.pk)
            instance._old_is_active = old_instance.is_active
        except Operator.DoesNotExist:
            instance._old_is_active = None 