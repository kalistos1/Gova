"""Reports app configuration."""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Configuration for the reports app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    verbose_name = 'Reports'
    
    def ready(self):
        """Connect signal handlers when app is ready."""
        import reports.signals  # noqa
