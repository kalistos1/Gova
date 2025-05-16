"""Middleware for request logging and role-based access control.

This module provides middleware classes for:
- Logging all API requests to AuditLog
- Enforcing role-based access control for endpoints
- Request/response modification for security

Example usage:
    MIDDLEWARE = [
        ...
        'core.middleware.LogRequestMiddleware',
        'core.middleware.RoleBasedAccessMiddleware',
    ]

    # Role-based access configuration in settings.py
    ROLE_BASED_ACCESS = {
        'reports': {
            'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
            'DELETE': ['STATE_OFFICIAL'],
        },
        'grants': {
            'POST': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
            'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
            'DELETE': ['STATE_OFFICIAL'],
        }
    }
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import AuditLog
from accounts.models import User

logger = logging.getLogger(__name__)

class LogRequestMiddleware:
    """Middleware for logging all API requests to AuditLog.
    
    This middleware logs:
    - All API requests and responses
    - User information
    - Request method and path
    - Response status and duration
    - Error details if any
    
    The logs are stored in the AuditLog model and can be used for:
    - Security auditing
    - Usage analytics
    - Debugging
    - Compliance reporting
    """
    
    def __init__(self, get_response: Callable):
        """Initialize middleware.
        
        Args:
            get_response: The next middleware in the chain
        """
        self.get_response = get_response
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and log it.
        
        Args:
            request: The HTTP request
            
        Returns:
            HttpResponse: The HTTP response
        """
        # Skip logging for non-API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
            
        # Get request details
        start_time = time.time()
        request_data = self._get_request_data(request)
        
        # Process request
        response = self.get_response(request)
        
        # Log request/response
        self._log_request(
            request=request,
            response=response,
            request_data=request_data,
            duration=time.time() - start_time
        )
        
        return response
        
    def _get_request_data(self, request: HttpRequest) -> dict:
        """Get request data for logging.
        
        Args:
            request: The HTTP request
            
        Returns:
            dict: Request data including:
                - method: HTTP method
                - path: Request path
                - query_params: Query parameters
                - user: User information
                - ip_address: Client IP
                - user_agent: Client user agent
                - timestamp: Request timestamp
                - body: Request body (for non-GET)
        """
        # Get user info
        user = request.user if hasattr(request, 'user') else None
        user_info = None
        if user and user.is_authenticated:
            user_info = {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
            
        # Get request data
        data = {
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET.items()),
            'user': user_info,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'timestamp': timezone.now().isoformat()
        }
        
        # Add request body for non-GET requests
        if request.method != 'GET':
            try:
                data['body'] = self._get_request_body(request)
            except Exception as e:
                logger.warning(f'Failed to get request body: {str(e)}')
                data['body'] = None
                
        return data
        
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address.
        
        Args:
            request: The HTTP request
            
        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')
        
    def _get_request_body(self, request: HttpRequest) -> Optional[dict]:
        """Get request body as dict.
        
        Args:
            request: The HTTP request
            
        Returns:
            Optional[dict]: Request body or None if not available
        """
        if hasattr(request, 'data'):
            return request.data
        elif request.content_type == 'application/json':
            try:
                import json
                return json.loads(request.body)
            except:
                return None
        return None
        
    def _log_request(
        self,
        request: HttpRequest,
        response: HttpResponse,
        request_data: dict,
        duration: float
    ) -> None:
        """Log the request and response.
        
        Args:
            request: The HTTP request
            response: The HTTP response
            request_data: Request data
            duration: Request duration in seconds
        """
        # Get endpoint info
        try:
            resolver_match = resolve(request.path)
            endpoint = f"{resolver_match.namespace}:{resolver_match.url_name}"
        except:
            endpoint = request.path
            
        # Get response data
        response_data = None
        if isinstance(response, Response):
            try:
                response_data = response.data
            except:
                pass
                
        # Create audit log entry
        try:
            AuditLog.objects.create(
                action=f'API_{request.method}',
                user=request.user if hasattr(request, 'user') else None,
                details={
                    'endpoint': endpoint,
                    'request': request_data,
                    'response': {
                        'status_code': response.status_code,
                        'data': response_data
                    },
                    'duration': duration
                }
            )
        except Exception as e:
            logger.error(f'Failed to create audit log: {str(e)}')
            
        # Log errors
        if response.status_code >= 400:
            logger.error(
                f'API Error: {endpoint}',
                extra={
                    'request': request_data,
                    'response': response_data,
                    'status_code': response.status_code,
                    'duration': duration
                }
            )

class RoleBasedAccessMiddleware:
    """Middleware for role-based access control.
    
    This middleware enforces role-based access control for API endpoints
    based on user roles and endpoint configuration.
    
    Configuration in settings.py:
    ROLE_BASED_ACCESS = {
        'app_name': {
            'HTTP_METHOD': ['ROLE1', 'ROLE2'],
            ...
        },
        ...
    }
    
    Example:
    ROLE_BASED_ACCESS = {
        'reports': {
            'PATCH': ['LGA_OFFICIAL', 'STATE_OFFICIAL'],
            'DELETE': ['STATE_OFFICIAL'],
        }
    }
    """
    
    def __init__(self, get_response: Callable):
        """Initialize middleware.
        
        Args:
            get_response: The next middleware in the chain
        """
        self.get_response = get_response
        self.role_access = getattr(settings, 'ROLE_BASED_ACCESS', {})
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and check role-based access.
        
        Args:
            request: The HTTP request
            
        Returns:
            HttpResponse: The HTTP response
            
        Raises:
            PermissionDenied: If user doesn't have required role
        """
        # Skip for non-API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
            
        # Skip for unauthenticated users (handled by DRF)
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)
            
        # Check role-based access
        try:
            self._check_role_access(request)
        except PermissionDenied as e:
            # Log access denied
            logger.warning(
                f'Role-based access denied: {request.user.email}',
                extra={
                    'user_id': request.user.id,
                    'role': request.user.role,
                    'path': request.path,
                    'method': request.method
                }
            )
            return Response(
                {
                    'error': str(e),
                    'code': 'permission_denied',
                    'required_role': getattr(e, 'required_role', None)
                },
                status=403
            )
            
        return self.get_response(request)
        
    def _check_role_access(self, request: HttpRequest) -> None:
        """Check if user has required role for the endpoint.
        
        Args:
            request: The HTTP request
            
        Raises:
            PermissionDenied: If user doesn't have required role
        """
        # Get endpoint info
        try:
            resolver_match = resolve(request.path)
            app_name = resolver_match.namespace
            if not app_name:
                app_name = resolver_match.url_name.split('-')[0]
        except:
            return  # Skip if can't resolve endpoint
            
        # Get role requirements for app and method
        app_roles = self.role_access.get(app_name, {})
        required_roles = app_roles.get(request.method, [])
        
        # Skip if no role requirements
        if not required_roles:
            return
            
        # Check user role
        user_role = getattr(request.user, 'role', None)
        if not user_role or user_role not in required_roles:
            error = PermissionDenied(
                f'This endpoint requires one of these roles: {", ".join(required_roles)}'
            )
            error.required_role = required_roles
            raise error 