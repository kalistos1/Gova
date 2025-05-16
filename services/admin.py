from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from .models import Service, ServiceRequest

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Admin configuration for Service model."""
    
    list_display = (
        'name', 'category', 'base_price', 'is_active',
        'created_at', 'updated_at'
    )
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'category', 'base_price')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['activate_services', 'deactivate_services']
    
    def activate_services(self, request, queryset):
        """Activate selected services."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _('Successfully activated %(count)d services.') % {'count': updated}
        )
    activate_services.short_description = _('Activate selected services')
    
    def deactivate_services(self, request, queryset):
        """Deactivate selected services."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            _('Successfully deactivated %(count)d services.') % {'count': updated}
        )
    deactivate_services.short_description = _('Deactivate selected services')

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    """Admin configuration for ServiceRequest model."""
    
    list_display = (
        'id', 'service_link', 'user_link', 'amount',
        'status_badge', 'payment_status_badge', 'created_at'
    )
    list_filter = (
        'status', 'payment_status', 'service__category',
        'created_at', 'completed_at'
    )
    search_fields = (
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'service__name', 'payment_reference'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'completed_at',
        'payment_reference', 'payment_link'
    )
    fieldsets = (
        (None, {
            'fields': ('user', 'service', 'location', 'landmark')
        }),
        (_('Payment Information'), {
            'fields': (
                'amount', 'payment_status', 'payment_reference',
                'payment_link'
            )
        }),
        (_('Request Status'), {
            'fields': ('status', 'notes', 'completed_at')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = [
        'mark_as_processing', 'mark_as_completed',
        'mark_as_cancelled', 'mark_as_rejected'
    ]
    
    def service_link(self, obj):
        """Create a link to the service detail page."""
        url = reverse('admin:services_service_change', args=[obj.service.id])
        return format_html('<a href="{}">{}</a>', url, obj.service.name)
    service_link.short_description = _('Service')
    service_link.admin_order_field = 'service__name'
    
    def user_link(self, obj):
        """Create a link to the user detail page."""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.get_full_name() or obj.user.username
        )
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'
    
    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'pending': 'gray',
            'processing': 'blue',
            'completed': 'green',
            'cancelled': 'red',
            'rejected': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    status_badge.admin_order_field = 'status'
    
    def payment_status_badge(self, obj):
        """Display payment status as a colored badge."""
        colors = {
            'pending': 'gray',
            'paid': 'green',
            'failed': 'red',
            'refunded': 'orange'
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = _('Payment Status')
    payment_status_badge.admin_order_field = 'payment_status'
    
    def mark_as_processing(self, request, queryset):
        """Mark selected requests as processing."""
        updated = queryset.update(status=ServiceRequest.Status.PROCESSING)
        self.message_user(
            request,
            _('Successfully marked %(count)d requests as processing.') % {'count': updated}
        )
    mark_as_processing.short_description = _('Mark selected requests as processing')
    
    def mark_as_completed(self, request, queryset):
        """Mark selected requests as completed."""
        from django.utils import timezone
        updated = queryset.update(
            status=ServiceRequest.Status.COMPLETED,
            completed_at=timezone.now()
        )
        self.message_user(
            request,
            _('Successfully marked %(count)d requests as completed.') % {'count': updated}
        )
    mark_as_completed.short_description = _('Mark selected requests as completed')
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected requests as cancelled."""
        updated = queryset.update(status=ServiceRequest.Status.CANCELLED)
        self.message_user(
            request,
            _('Successfully marked %(count)d requests as cancelled.') % {'count': updated}
        )
    mark_as_cancelled.short_description = _('Mark selected requests as cancelled')
    
    def mark_as_rejected(self, request, queryset):
        """Mark selected requests as rejected."""
        updated = queryset.update(status=ServiceRequest.Status.REJECTED)
        self.message_user(
            request,
            _('Successfully marked %(count)d requests as rejected.') % {'count': updated}
        )
    mark_as_rejected.short_description = _('Mark selected requests as rejected')
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of service requests."""
        return False
