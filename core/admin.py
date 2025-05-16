"""Admin interface for core app models."""

from django.contrib import admin
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import Reward, AuditLog

@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    """Admin interface for Reward model.
    
    Features:
    - List display with status colors
    - Filtering and search
    - Batch actions
    - Statistics
    - Retry failed rewards
    - Export functionality
    """
    
    list_display = (
        'id', 'user', 'amount', 'action_type', 'status_badge',
        'created_at', 'processed_at', 'failure_reason'
    )
    list_filter = ('status', 'action_type', 'created_at', 'processed_at')
    search_fields = (
        'user__email', 'user__phone_number', 'reference_id',
        'failure_reason'
    )
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'processed_at',
        'failure_reason', 'reference_id', 'reference_type'
    )
    actions = ['retry_failed_rewards', 'export_rewards']
    
    fieldsets = (
        ('Reward Information', {
            'fields': (
                'id', 'user', 'amount', 'action_type',
                'reference_id', 'reference_type'
            )
        }),
        ('Status Information', {
            'fields': (
                'status', 'processed_at', 'failure_reason'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'PENDING': 'orange',
            'PROCESSED': 'green',
            'FAILED': 'red'
        }
        return format_html(
            '<span style="color: white; background-color: {}; '
            'padding: 5px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        """Add annotations for statistics."""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to the changelist view."""
        extra_context = extra_context or {}
        
        # Get statistics
        stats = Reward.objects.aggregate(
            total_rewards=Count('id'),
            total_amount=Sum('amount'),
            avg_amount=Avg('amount'),
            pending_count=Count('id', filter=models.Q(status='PENDING')),
            processed_count=Count('id', filter=models.Q(status='PROCESSED')),
            failed_count=Count('id', filter=models.Q(status='FAILED'))
        )
        
        # Add to context
        extra_context['stats'] = {
            'Total Rewards': stats['total_rewards'],
            'Total Amount': f"NGN {stats['total_amount']:,.2f}",
            'Average Amount': f"NGN {stats['avg_amount']:,.2f}",
            'Pending Rewards': stats['pending_count'],
            'Processed Rewards': stats['processed_count'],
            'Failed Rewards': stats['failed_count']
        }
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def retry_failed_rewards(self, request, queryset):
        """Retry processing failed rewards."""
        from core.services import RewardProcessor
        
        processor = RewardProcessor()
        success_count = 0
        failure_count = 0
        
        for reward in queryset.filter(status='FAILED'):
            try:
                if processor.process_reward(reward):
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Error processing reward {reward.id}: {str(e)}',
                    level='ERROR'
                )
                failure_count += 1
        
        self.message_user(
            request,
            f'Retry complete: {success_count} succeeded, {failure_count} failed'
        )
    retry_failed_rewards.short_description = 'Retry selected failed rewards'
    
    def export_rewards(self, request, queryset):
        """Export selected rewards to CSV."""
        import csv
        from django.http import HttpResponse
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="rewards_export_{datetime.now():%Y%m%d_%H%M%S}.csv"'
        )
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User', 'Amount', 'Action Type', 'Status',
            'Created At', 'Processed At', 'Failure Reason'
        ])
        
        for reward in queryset:
            writer.writerow([
                reward.id,
                reward.user.email if reward.user else 'N/A',
                reward.amount,
                reward.get_action_type_display(),
                reward.get_status_display(),
                reward.created_at,
                reward.processed_at,
                reward.failure_reason
            ])
        
        return response
    export_rewards.short_description = 'Export selected rewards to CSV'

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model."""
    
    list_display = ('timestamp', 'user', 'action', 'entity', 'entity_id')
    list_filter = ('action', 'entity', 'timestamp')
    search_fields = ('user__email', 'action', 'entity', 'details')
    readonly_fields = ('id', 'timestamp', 'details_formatted')
    
    def details_formatted(self, obj):
        """Format JSON details for display."""
        if not obj.details:
            return '-'
        import json
        return format_html(
            '<pre>{}</pre>',
            json.dumps(obj.details, indent=2)
        )
    details_formatted.short_description = 'Details'
