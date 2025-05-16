"""Admin interface for the reports app."""

from django.contrib import admin
# from django.contrib.gis.admin import OSMGeoAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Report, ReportComment, AuditLog

# @admin.register(Report)
# class ReportAdmin(OSMGeoAdmin):
#     """Admin interface for managing issue reports."""
    
#     list_display = (
#         'title', 'category', 'status', 'priority', 'lga',
#         'payment_status', 'nin_verified', 'created_at', 'reporter',
#         'view_comments'
#     )
#     list_filter = (
#         'category', 'status', 'priority', 'lga', 'created_at',
#         'is_anonymous', 'payment_status', 'nin_verified',
#         'submission_channel', 'submission_language'
#     )
#     search_fields = (
#         'title', 'description', 'address', 'transaction_reference',
#         'transaction_id', 'reporter__email', 'reporter__phone'
#     )
#     readonly_fields = (
#         'id', 'created_at', 'updated_at', 'upvotes',
#         'transaction_reference', 'transaction_id', 'payment_date',
#         'nin_verification_date', 'ai_summary', 'ai_priority_score',
#         'view_audit_logs'
#     )
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('title', 'description', 'category', 'priority', 'status')
#         }),
#         ('Location', {
#             'fields': ('location', 'address', 'lga', 'landmark')
#         }),
#         ('Media', {
#             'fields': ('images', 'videos', 'voice_notes', 'view_media'),
#             'classes': ('collapse',)
#         }),
#         ('Reporter Information', {
#             'fields': ('reporter', 'is_anonymous', 'assigned_to')
#         }),
#         ('Payment Information', {
#             'fields': (
#                 'payment_status', 'payment_amount', 'transaction_reference',
#                 'transaction_id', 'payment_date'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Verification', {
#             'fields': ('nin_verified', 'nin_verification_date'),
#             'classes': ('collapse',)
#         }),
#         ('Submission Details', {
#             'fields': (
#                 'submission_channel', 'submission_language',
#                 'original_text', 'device_info', 'offline_sync_id'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('AI Analysis', {
#             'fields': ('ai_summary', 'ai_priority_score'),
#             'classes': ('collapse',)
#         }),
#         ('System Fields', {
#             'fields': ('id', 'created_at', 'updated_at', 'upvotes', 'view_audit_logs'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     def get_queryset(self, request):
#         """Optimize admin list view queries."""
#         return super().get_queryset(request).select_related(
#             'reporter', 'lga', 'assigned_to'
#         ).prefetch_related('comments', 'audit_logs')
    
#     def view_comments(self, obj):
#         """Display link to view comments."""
#         count = obj.comments.count()
#         url = reverse('admin:reports_reportcomment_changelist')
#         return format_html(
#             '<a href="{}?report__id__exact={}">{} comments</a>',
#             url, obj.id, count
#         )
#     view_comments.short_description = 'Comments'
    
#     def view_audit_logs(self, obj):
#         """Display audit logs in admin."""
#         logs = obj.audit_logs.all()
#         if not logs:
#             return "No audit logs"
        
#         html = ['<table style="width:100%">']
#         html.append('<tr><th>Time</th><th>User</th><th>Action</th></tr>')
#         for log in logs:
#             html.append(
#                 f'<tr><td>{log.created_at}</td>'
#                 f'<td>{log.user or "System"}</td>'
#                 f'<td>{log.action}</td></tr>'
#             )
#         html.append('</table>')
#         return mark_safe(''.join(html))
#     view_audit_logs.short_description = 'Audit Logs'
    
#     def view_media(self, obj):
#         """Display media files in admin."""
#         html = []
        
#         if obj.images:
#             html.append('<h4>Images:</h4>')
#             for image in obj.images:
#                 html.append(
#                     f'<img src="{image}" style="max-width:200px;margin:5px">'
#                 )
        
#         if obj.videos:
#             html.append('<h4>Videos:</h4>')
#             for video in obj.videos:
#                 html.append(
#                     f'<video controls style="max-width:200px;margin:5px">'
#                     f'<source src="{video}" type="video/mp4">'
#                     f'</video>'
#                 )
        
#         if obj.voice_notes:
#             html.append('<h4>Voice Notes:</h4>')
#             for voice in obj.voice_notes:
#                 html.append(
#                     f'<audio controls style="margin:5px">'
#                     f'<source src="{voice}" type="audio/mpeg">'
#                     f'</audio>'
#                 )
        
#         return mark_safe(''.join(html)) if html else "No media files"
#     view_media.short_description = 'Media Preview'

# @admin.register(ReportComment)
# class ReportCommentAdmin(admin.ModelAdmin):
#     """Admin interface for managing report comments."""
    
#     list_display = ('report', 'user', 'is_official', 'created_at')
#     list_filter = ('is_official', 'created_at')
#     search_fields = ('content', 'user__email', 'report__title')
#     readonly_fields = ('created_at', 'updated_at')
    
#     def get_queryset(self, request):
#         """Optimize admin list view queries."""
#         return super().get_queryset(request).select_related('report', 'user')

# @admin.register(AuditLog)
# class AuditLogAdmin(admin.ModelAdmin):
#     """Admin interface for viewing audit logs."""
    
#     list_display = ('report', 'action', 'user', 'created_at')
#     list_filter = ('action', 'created_at')
#     search_fields = ('report__title', 'user__email', 'action')
#     readonly_fields = ('created_at', 'old_value', 'new_value')
    
#     def get_queryset(self, request):
#         """Optimize admin list view queries."""
#         return super().get_queryset(request).select_related('report', 'user')
    
#     def has_add_permission(self, request):
#         """Disable manual creation of audit logs."""
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         """Disable editing of audit logs."""
#         return False
    
#     def has_delete_permission(self, request, obj=None):
#         """Disable deletion of audit logs."""
#         return False
