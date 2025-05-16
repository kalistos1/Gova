"""Push notification handlers for the reports app."""

from django.conf import settings
from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)

class PushNotificationHandler:
    """Handler for sending push notifications."""
    
    @staticmethod
    def send_to_user(user, title, body, data=None):
        """Send push notification to a specific user.
        
        Args:
            user: User object
            title: Notification title
            body: Notification body
            data: Optional data payload
        """
        try:
            # Get user's FCM tokens
            tokens = user.fcm_tokens.filter(is_active=True).values_list('token', flat=True)
            
            if not tokens:
                return
                
            # Create message
            message = messaging.MulticastMessage(
                tokens=list(tokens),
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='notification_icon',
                        color='#4CAF50',
                        sound='default'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1
                        )
                    )
                )
            )
            
            # Send message
            response = messaging.send_multicast(message)
            
            # Handle failed tokens
            if response.failure_count > 0:
                failed_tokens = []
                for idx, result in enumerate(response.responses):
                    if not result.success:
                        failed_tokens.append(tokens[idx])
                        
                # Deactivate failed tokens
                user.fcm_tokens.filter(token__in=failed_tokens).update(is_active=False)
                
        except Exception as e:
            logger.error(f'Error sending push notification: {str(e)}')
    
    @staticmethod
    def send_to_topic(topic, title, body, data=None):
        """Send push notification to a topic.
        
        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Optional data payload
        """
        try:
            # Create message
            message = messaging.Message(
                topic=topic,
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='notification_icon',
                        color='#4CAF50',
                        sound='default'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1
                        )
                    )
                )
            )
            
            # Send message
            messaging.send(message)
            
        except Exception as e:
            logger.error(f'Error sending topic notification: {str(e)}')
    
    @classmethod
    def notify_report_status_change(cls, report):
        """Send notification when report status changes."""
        if report.reporter:
            cls.send_to_user(
                report.reporter,
                'Report Status Update',
                f'Your report "{report.title}" is now {report.get_status_display()}',
                {
                    'report_id': str(report.id),
                    'status': report.status
                }
            )
    
    @classmethod
    def notify_report_assignment(cls, report):
        """Send notification when report is assigned."""
        if report.assigned_to:
            cls.send_to_user(
                report.assigned_to,
                'New Report Assignment',
                f'You have been assigned to report: {report.title}',
                {
                    'report_id': str(report.id),
                    'type': 'assignment'
                }
            )
    
    @classmethod
    def notify_payment_status(cls, report):
        """Send notification about payment status."""
        if report.reporter:
            cls.send_to_user(
                report.reporter,
                'Payment Update',
                f'Payment for report "{report.title}" is {report.get_payment_status_display()}',
                {
                    'report_id': str(report.id),
                    'payment_status': report.payment_status
                }
            ) 