"""URL configuration for API endpoints.

This module defines the URL patterns for the API endpoints,
including authentication, user management, and other core functionality.

The URL patterns are organized as follows:
- Authentication endpoints (/api/v1/auth/*)
  - NIN verification and login
  - JWT token management (refresh, verify, blacklist)
  - Password management (reset, change)
  - Session management (logout)
- User management endpoints (/api/v1/users/*)
- Other app endpoints (/api/v1/*)

Example usage:
    # NIN verification
    POST /api/v1/auth/nin/verify/
    {
        "nin": "12345678901",
        "phone": "+2348012345678"
    }

    # Token refresh
    POST /api/v1/auth/token/refresh/
    {
        "refresh": "jwt.refresh.token"
    }

    # Token blacklist
    POST /api/v1/auth/token/blacklist/
    {
        "refresh": "jwt.refresh.token"
    }

    # Password reset request
    POST /api/v1/auth/password/reset/
    {
        "email": "user@example.com"
    }

    # Password reset confirm
    POST /api/v1/auth/password/reset/confirm/
    {
        "token": "reset.token",
        "password": "new_password"
    }
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
    TokenBlacklistView
)

from .views import (
    verify_nin_and_login,
    PasswordResetRequestView,
    PasswordChangeView,
    PasswordResetConfirmView,
    LogoutView,
    health_check,
    api_documentation
)

app_name = 'api'

# Router for viewset endpoints
router = DefaultRouter()

# Authentication URL patterns
auth_urlpatterns = [
    # NIN verification endpoint with improved validation
    path('nin/verify/', verify_nin_and_login, name='nin-verify'),
    
    # JWT token management with enhanced security
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token-blacklist'),
    
    # Password management with stronger validation
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
    
    # Session management with device tracking
    path('logout/', LogoutView.as_view(), name='logout'),
]

# API URL patterns
urlpatterns = [
    # Authentication endpoints
    path('auth/', include((auth_urlpatterns, 'auth'))),
    
    # Include app URLs
    path('', include('accounts.urls')),
    path('', include('reports.urls')),
    path('', include('proposals.urls')),
    path('', include('services.urls')),
    path('', include('engagement.urls')),
    # path('', include('grants.urls')),
    # path('admin/', include('api.admin.urls')),
    
    # Utility endpoints
    path('health/', health_check.as_view(), name='health_check'),
    path('docs/', api_documentation.as_view(), name='api_docs'),
]
