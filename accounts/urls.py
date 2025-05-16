from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView, TokenBlacklistView
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.user_register, name='register'),
    path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    path('auth/token/blacklist/', TokenBlacklistView.as_view(), name='token-blacklist'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/nin/verify/', views.verify_nin, name='verify-nin'),
    
    # Password management
    path('auth/password/reset/request/', views.request_password_reset, name='request-password-reset'),
    path('auth/password/reset/confirm/', views.reset_password, name='reset-password'),
    path('auth/password/change/', views.change_password_view, name='change-password'),
    
    # Email verification
    path('auth/email/verify/', views.verify_email, name='verify-email'),
    path('auth/email/resend/', views.resend_verification, name='resend-verification'),
    
    # User profile
    path('users/me/', views.get_user_profile, name='user-profile'),
    path('users/me/update/', views.update_profile, name='update-profile'),
    
    # User management (admin only)
    path('users/', views.user_list, name='user-list'),
    path('users/<uuid:user_id>/', views.user_detail, name='user-detail'),
    path('users/<uuid:user_id>/status/', views.toggle_user_status, name='toggle-user-status'),
    path('users/<uuid:user_id>/role/', views.update_user_role, name='update-user-role'),
    path('users/official/create/', views.create_official_account, name='create-official'),
    
    # Rewards
    path('rewards/', views.list_user_rewards, name='user-rewards'),
    
    # Kiosks
    path('kiosks/', views.list_kiosks, name='list-kiosks'),
    
    # Sync logs
    path('sync-logs/', views.create_sync_log, name='create-sync-log'),
]

"""
URL Patterns:
    - POST /api/v1/auth/nin/verify/:
        Verifies a user's National Identification Number (NIN).
        View: views.verify_nin

    - GET /api/v1/users/me/:
        Retrieves the profile of the currently authenticated user.
        View: views.get_user_profile

    - GET /api/v1/rewards/:
        Retrieves a list of all rewards for the authenticated user.
        View: views.list_user_rewards

    - GET /api/v1/kiosks/:
        Retrieves a list of all kiosks.
        View: views.list_kiosks

    - POST /api/v1/sync-logs/:
        Creates a new sync log entry.
        View: views.create_sync_log
"""