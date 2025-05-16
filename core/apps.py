"""Core app configuration.

This module defines the configuration for the core app, which provides essential
functionality for the AbiaHub platform including reward processing, audit logging,
and location management.
"""

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    """Configuration for the core app.
    
    This app provides core functionality for the AbiaHub platform, including:
    - Reward system for user actions (proposals, votes, etc.)
    - Audit logging for system events
    - Location management for kiosks
    - Notification system for rewards and system events
    
    The app also handles signal connections for:
    - Reward processing
    - Audit logging
    - User activity tracking
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core'
    
    def ready(self):
        """Initialize the app when Django is ready.
        
        This method is called when Django has finished loading all apps and
        is ready to serve requests. It:
        1. Imports and connects signal handlers
        2. Sets up any necessary app-level initialization
        3. Logs any errors during signal loading without preventing app startup
        
        Raises:
            ImportError: If signals module cannot be imported (logged but not raised)
        """
        try:
            # Import signals to register them
            import core.signals  # noqa: F401
            logger.info('Core signals loaded successfully')
        except ImportError as e:
            logger.error(
                'Failed to load core signals: %s. '
                'Some functionality may be limited.',
                str(e)
            )
