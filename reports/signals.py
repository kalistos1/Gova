"""Signal handlers for the reports app."""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from .models import Report, ReportComment, AuditLog
from .integrations import OpenRouterAI, AfricasTalkingClient
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(pre_save, sender=Report)
def handle_report_pre_save(sender, instance, **kwargs):
    """Handle report pre-save operations.
    
    - Generate AI summary and priority if enabled
    - Extract location from image EXIF if available
    - Sanitize phone numbers
    - Handle translations
    """
    try:
        if not instance.pk:  # New report
            # AI processing
            if settings.ENABLE_AI_PROCESSING:
                ai_client = OpenRouterAI()
                summary = ai_client.generate_summary(instance.description)
                priority = ai_client.calculate_priority(instance.description)
                
                if summary:
                    instance.ai_summary = summary
                if priority:
                    instance.ai_priority_score = priority
                    
                    # Update priority based on AI score
                    if priority >= 0.8:
                        instance.priority = 'URGENT'
                    elif priority >= 0.6:
                        instance.priority = 'HIGH'
                    elif priority >= 0.4:
                        instance.priority = 'MEDIUM'
                    else:
                        instance.priority = 'LOW'
            
            # Extract location from first image if available
            if instance.images and not instance.location:
                from .utils import extract_location_from_exif
                instance.location = extract_location_from_exif(instance.images[0])
            
            # Sanitize phone number if available
            if hasattr(instance, 'phone_number'):
                from .utils import sanitize_phone_number
                instance.phone_number = sanitize_phone_number(instance.phone_number)
            
            # Handle translation if needed
            if instance.submission_language != 'en':
                from .utils import translate_text
                instance.original_text = instance.description
                instance.description = translate_text(
                    instance.description,
                    instance.submission_language,
                    'en'
                )
    
    except Exception as e:
        logger.error(f'Error in report pre-save signal: {str(e)}')

@receiver(post_save, sender=Report)
def handle_report_post_save(sender, instance, created, **kwargs):
    """Handle report post-save operations.
    
    - Create audit log entry
    - Send notifications
    - Update cache
    """
    try:
        # Create audit log entry
        if created:
            AuditLog.objects.create(
                report=instance,
                action='Report Created',
                user=instance.reporter,
                new_value={
                    'title': instance.title,
                    'description': instance.description,
                    'category': instance.category,
                    'priority': instance.priority,
                    'status': instance.status
                }
            )
        
        # Send notifications
        if instance.submission_channel in ['USSD', 'SMS']:
            sms_client = AfricasTalkingClient()
            message = f"Your report (ID: {instance.id}) has been received. "
            message += f"Current status: {instance.get_status_display()}"
            
            if instance.reporter and instance.reporter.phone:
                sms_client.send_sms(
                    to=instance.reporter.phone,
                    message=message
                )
        
        # Update cache
        cache_key = f'report_{instance.id}'
        cache.delete(cache_key)  # Invalidate cache
        
    except Exception as e:
        logger.error(f'Error in report post-save signal: {str(e)}')

@receiver(post_save, sender=ReportComment)
def handle_comment_post_save(sender, instance, created, **kwargs):
    """Handle comment post-save operations.
    
    - Create audit log entry
    - Send notifications
    - Update cache
    """
    try:
        if created:
            # Create audit log entry
            AuditLog.objects.create(
                report=instance.report,
                action='Comment Added',
                user=instance.user,
                new_value={'content': instance.content}
            )
            
            # Send notification to report owner
            if (instance.report.reporter and 
                instance.report.reporter.phone and 
                instance.is_official):
                sms_client = AfricasTalkingClient()
                message = f"Official update on your report (ID: {instance.report.id}): "
                message += instance.content[:100] + "..."
                
                sms_client.send_sms(
                    to=instance.report.reporter.phone,
                    message=message
                )
            
            # Update cache
            cache_key = f'report_{instance.report.id}'
            cache.delete(cache_key)
            
    except Exception as e:
        logger.error(f'Error in comment post-save signal: {str(e)}')

@receiver(post_delete, sender=Report)
def handle_report_post_delete(sender, instance, **kwargs):
    """Handle report post-delete operations.
    
    - Create audit log entry
    - Clean up files
    - Update cache
    """
    try:
        # Create audit log entry
        AuditLog.objects.create(
            report=instance,
            action='Report Deleted',
            user=instance.reporter
        )
        
        # Clean up files
        if instance.images:
            from django.core.files.storage import default_storage
            for image in instance.images:
                try:
                    default_storage.delete(image)
                except Exception as e:
                    logger.error(f'Error deleting image {image}: {str(e)}')
        
        if instance.videos:
            for video in instance.videos:
                try:
                    default_storage.delete(video)
                except Exception as e:
                    logger.error(f'Error deleting video {video}: {str(e)}')
        
        if instance.voice_notes:
            for voice_note in instance.voice_notes:
                try:
                    default_storage.delete(voice_note)
                except Exception as e:
                    logger.error(f'Error deleting voice note {voice_note}: {str(e)}')
        
        # Update cache
        cache_key = f'report_{instance.id}'
        cache.delete(cache_key)
        
    except Exception as e:
        logger.error(f'Error in report post-delete signal: {str(e)}') 