"""Management command to process pending rewards.

This command processes pending rewards in batches, sending airtime via Africa's Talking
and handling notifications for both successful and failed rewards.
"""

import logging
import time
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from core.services import RewardProcessor

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Command to process pending rewards."""
    
    help = 'Process pending rewards in batches'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--batch-size',
            type=int,
            default=settings.REWARD_PROCESSING_BATCH_SIZE,
            help='Number of rewards to process in one batch'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=settings.REWARD_PROCESSING_DELAY,
            help='Delay between batches in seconds'
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously until interrupted'
        )
        parser.add_argument(
            '--max-batches',
            type=int,
            help='Maximum number of batches to process'
        )
    
    def handle(self, *args, **options):
        """Handle the command."""
        processor = RewardProcessor()
        batch_size = options['batch_size']
        delay = options['delay']
        continuous = options['continuous']
        max_batches = options['max_batches']
        
        # Override batch size if specified
        if batch_size != settings.REWARD_PROCESSING_BATCH_SIZE:
            processor.batch_size = batch_size
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting reward processing (batch size: {batch_size}, '
                f'delay: {delay}s, continuous: {continuous})'
            )
        )
        
        batch_count = 0
        total_processed = total_failed = total_skipped = 0
        
        try:
            while True:
                # Check if we've reached max batches
                if max_batches and batch_count >= max_batches:
                    self.stdout.write(
                        self.style.SUCCESS(f'Reached maximum batch count ({max_batches})')
                    )
                    break
                
                # Process batch
                processed, failed, skipped = processor.process_pending_rewards()
                
                # Update totals
                total_processed += processed
                total_failed += failed
                total_skipped += skipped
                batch_count += 1
                
                # Log batch results
                self.stdout.write(
                    f'Batch {batch_count}: '
                    f'{processed} processed, {failed} failed, {skipped} skipped'
                )
                
                # Check if we should continue
                if not continuous:
                    break
                    
                # Check if there are more rewards to process
                if processed + failed + skipped == 0:
                    self.stdout.write('No more rewards to process')
                    break
                    
                # Wait before next batch
                if delay > 0:
                    time.sleep(delay)
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nProcessing interrupted by user'))
        except Exception as e:
            raise CommandError(f'Error processing rewards: {str(e)}')
        finally:
            # Print summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nProcessing complete:\n'
                    f'Total batches: {batch_count}\n'
                    f'Total processed: {total_processed}\n'
                    f'Total failed: {total_failed}\n'
                    f'Total skipped: {total_skipped}'
                )
            ) 