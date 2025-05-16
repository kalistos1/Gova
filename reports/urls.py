"""URL patterns for the reports app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'reports'

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'reports', views.ReportViewSet, basename='report')
router.register(r'verify', views.VerificationViewSet, basename='verify')
router.register(r'ussd', views.USSDViewSet, basename='ussd')
router.register(r'sms', views.SMSViewSet, basename='sms')
router.register(r'media', views.MediaUploadViewSet, basename='media')

# Additional URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Report-specific endpoints
    path('reports/<uuid:pk>/comments/', views.ReportViewSet.as_view({'post': 'add_comment'}), name='report-comments'),
    path('reports/<uuid:pk>/upvote/', views.ReportViewSet.as_view({'post': 'upvote'}), name='report-upvote'),
    path('reports/<uuid:pk>/translate/', views.ReportViewSet.as_view({'post': 'translate'}), name='report-translate'),
    path('reports/<uuid:pk>/assign/', views.ReportViewSet.as_view({'post': 'assign'}), name='report-assign'),
    
    # Media upload endpoints
    path('media/image/', views.MediaUploadViewSet.as_view({'post': 'upload_image'}), name='upload-image'),
    path('media/video/', views.MediaUploadViewSet.as_view({'post': 'upload_video'}), name='upload-video'),
    path('media/voice/', views.MediaUploadViewSet.as_view({'post': 'upload_voice'}), name='upload-voice'),
    
    # Payment endpoints
    path('payments/initialize/', views.PaymentViewSet.as_view({'post': 'initialize'}), name='initialize-payment'),
    path('payments/verify/', views.PaymentViewSet.as_view({'post': 'verify'}), name='verify-payment'),
    path('payments/webhook/', views.PaymentViewSet.as_view({'post': 'webhook'}), name='payment-webhook'),
    
    # Verification endpoints
    path('verify/nin/', views.VerificationViewSet.as_view({'post': 'verify_nin'}), name='verify-nin'),
    path('verify/bvn/', views.VerificationViewSet.as_view({'post': 'verify_bvn'}), name='verify-bvn'),
    path('verify/phone/', views.VerificationViewSet.as_view({'post': 'verify_phone'}), name='verify-phone'),
    
    # Communication endpoints
    path('sms/send/', views.SMSViewSet.as_view({'post': 'send_sms'}), name='send-sms'),
    path('ussd/callback/', views.USSDViewSet.as_view({'post': 'callback'}), name='ussd-callback'),
]

# API endpoint documentation:
# /api/v1/reports/
#   GET: List all reports
#   POST: Create a new report
#
# /api/v1/reports/{id}/
#   GET: Retrieve a report
#   PATCH: Update a report
#   DELETE: Delete a report
#
# /api/v1/reports/{id}/comments/
#   POST: Add a comment to a report
#
# /api/v1/reports/{id}/upvote/
#   POST: Upvote a report
#
# /api/v1/reports/{id}/translate/
#   POST: Translate report content
#
# /api/v1/reports/{id}/assign/
#   POST: Assign report to official
#
# /api/v1/media/image/
#   POST: Upload report image
#
# /api/v1/media/video/
#   POST: Upload report video
#
# /api/v1/media/voice/
#   POST: Upload voice note
#
# /api/v1/payments/initialize/
#   POST: Initialize payment
#
# /api/v1/payments/verify/
#   POST: Verify payment
#
# /api/v1/payments/webhook/
#   POST: Handle payment webhook
#
# /api/v1/verify/nin/
#   POST: Verify NIN
#
# /api/v1/verify/bvn/
#   POST: Verify BVN
#
# /api/v1/verify/phone/
#   POST: Verify phone number
#
# /api/v1/sms/send/
#   POST: Send SMS message
#
# /api/v1/ussd/callback/
#   POST: Handle USSD callback
