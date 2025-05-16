"""Management command for cleaning up AI cache.

This command:
1. Cleans up expired cache entries for:
   - Report priorities
   - Message transcripts
   - Sentiment analysis
   - Report categories
2. Optionally forces cleanup of all cache entries
3. Logs cleanup statistics
"""

import logging
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q

from core.models import Report, Message, AuditLog

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Command for cleaning up AI cache."""
    
    help = 'Clean up expired AI cache entries'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup of all cache entries'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without actually cleaning'
        )
        
    def handle(self, *args: Any, **options: Any) -> None:
        """Handle command execution."""
        force = options['force']
        dry_run = options['dry_run']
        
        # Get cache keys
        keys = cache.keys('*')
        
        # Filter AI cache keys
        ai_keys = [
            k for k in keys
            if any(
                k.startswith(prefix)
                for prefix in [
                    'report_priority_',
                    'message_transcript_',
                    'report_sentiment_',
                    'report_category_'
                ]
            )
        ]
        
        if not ai_keys:
            self.stdout.write('No AI cache entries found')
            return
            
        # Get cache stats
        stats = {
            'total': len(ai_keys),
            'report_priority': len([k for k in ai_keys if k.startswith('report_priority_')]),
            'message_transcript': len([k for k in ai_keys if k.startswith('message_transcript_')]),
            'report_sentiment': len([k for k in ai_keys if k.startswith('report_sentiment_')]),
            'report_category': len([k for k in ai_keys if k.startswith('report_category_')])
        }
        
        # Log stats
        self.stdout.write('Cache statistics:')
        for key, count in stats.items():
            self.stdout.write(f'  {key}: {count}')
            
        if dry_run:
            self.stdout.write('\nDry run - no changes made')
            return
            
        # Clean cache
        if force:
            # Delete all AI cache entries
            cache.delete_many(ai_keys)
            self.stdout.write(f'\nDeleted {len(ai_keys)} cache entries')
        else:
            # Delete expired entries
            deleted = 0
            for key in ai_keys:
                if not cache.get(key):
                    cache.delete(key)
                    deleted += 1
            self.stdout.write(f'\nDeleted {deleted} expired cache entries')
            
        # Log cleanup
        AuditLog.objects.create(
            action='AI_CACHE_CLEANUP',
            details={
                'force': force,
                'dry_run': dry_run,
                'stats': stats,
                'deleted': len(ai_keys) if force else deleted
            }
        ) 