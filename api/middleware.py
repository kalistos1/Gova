"""Middleware for API rate limiting and audit logging.

This module provides middleware classes for:
- Rate limiting API requests
- Audit logging of API requests and responses
- Request/response validation and sanitization
- Request/response modification for security
"""

import logging
import time
import re
import json
from typing import Any, Callable, Dict, Optional
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import Throttled, ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import AuditLog

logger = logging.getLogger(__name__)

class RequestValidationMiddleware:
    """Middleware for validating and sanitizing API requests/responses.
    
    This middleware:
    - Validates request headers and content
    - Sanitizes request/response data
    - Blocks malicious requests
    - Adds security headers to responses
    """
    
    BLOCKED_PATTERNS = [
        r'(?i)(select|insert|update|delete|drop|union|exec|eval)\s',  # SQL/NoSQL injection
        r'(?i)<script.*?>.*?</script.*?>',  # XSS
        r'(?i)javascript:',  # XSS
        r'(?i)data:.*?base64',  # Data URI exploits
        r'(?i)(\.\./|\.\.\\)',  # Path traversal
    ]
    
    ALLOWED_CONTENT_TYPES = {
        'application/json',
        'multipart/form-data',
        'application/x-www-form-urlencoded'
    }
    
    REQUIRED_HEADERS = {
        'Content-Type',
        'Accept',
        'X-Request-ID'
    }
    
    def __init__(self, get_response: Callable):
        """Initialize middleware.
        
        Args:
            get_response: The next middleware in the chain
        """
        self.get_response = get_response
        
    def __call__(self, request: Request) -> Response:
        """Process the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            Response: The HTTP response
            
        Raises:
            ValidationError: If request validation fails
        """
        try:
            # Skip validation for non-API requests
            if not request.path.startswith('/api/'):
                return self.get_response(request)
                
            # Validate request
            self._validate_request(request)
            
            # Get response
            response = self.get_response(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            return response
            
        except ValidationError as e:
            logger.warning(
                'Request validation failed',
                extra={
                    'path': request.path,
                    'method': request.method,
                    'error': str(e)
                }
            )
            return Response(
                {'error': str(e)},
                status=400
            )
        except Exception as e:
            logger.error(
                'Request validation error',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return self.get_response(request)
            
    def _validate_request(self, request: Request) -> None:
        """Validate the HTTP request.
        
        Args:
            request: The HTTP request
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate headers
        content_type = request.headers.get('Content-Type', '')
        if not any(ct in content_type for ct in self.ALLOWED_CONTENT_TYPES):
            raise ValidationError(_('Invalid Content-Type header'))
            
        for header in self.REQUIRED_HEADERS:
            if header not in request.headers:
                raise ValidationError(_(f'Missing required header: {header}'))
                
        # Validate request body
        if request.method in ['POST', 'PUT', 'PATCH']:
            if not request.body:
                raise ValidationError(_('Request body is required'))
                
            # Check for malicious patterns
            body_str = request.body.decode('utf-8')
            for pattern in self.BLOCKED_PATTERNS:
                if re.search(pattern, body_str):
                    raise ValidationError(_('Invalid request content'))
                    
            # Validate JSON
            if 'application/json' in content_type:
                try:
                    json.loads(body_str)
                except json.JSONDecodeError:
                    raise ValidationError(_('Invalid JSON format'))
                    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response.
        
        Args:
            response: The HTTP response
        """
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Feature-Policy'] = "microphone 'none'; camera 'none'"

class RateLimitMiddleware:
    """Middleware for rate limiting API requests.
    
    This middleware implements rate limiting based on:
    - IP address
    - User ID (if authenticated)
    - Endpoint path
    
    Rate limits are configured in settings.RATE_LIMITS as:
    {
        'default': '100/hour',
        'auth': {
            'nin-verify': '5/hour',
            'token-refresh': '30/minute',
            'password-reset': '3/hour'
        }
    }
    """
    
    def __init__(self, get_response: Callable):
        """Initialize middleware.
        
        Args:
            get_response: The next middleware in the chain
        """
        self.get_response = get_response
        self.rate_limits = getattr(settings, 'RATE_LIMITS', {
            'default': '100/hour',
            'auth': {
                'nin-verify': '5/hour',
                'token-refresh': '30/minute',
                'password-reset': '3/hour'
            }
        })
        
    def __call__(self, request: Request) -> Response:
        """Process the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            Response: The HTTP response
            
        Raises:
            Throttled: If rate limit is exceeded
        """
        try:
            # Skip rate limiting for non-API requests
            if not request.path.startswith('/api/'):
                return self.get_response(request)
                
            # Skip rate limiting for staff/admin users
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.is_staff or request.user.is_superuser:
                    return self.get_response(request)
            
            # Get rate limit key
            key = self._get_rate_limit_key(request)
            if not key:
                return self.get_response(request)
                
            # Check rate limit
            if not self._check_rate_limit(key, request):
                retry_after = self._get_retry_after(key)
                logger.warning(
                    'Rate limit exceeded',
                    extra={
                        'path': request.path,
                        'method': request.method,
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'ip': request.META.get('REMOTE_ADDR'),
                        'retry_after': retry_after
                    }
                )
                raise Throttled(
                    detail={
                        'error': 'Rate limit exceeded',
                        'code': 'rate_limit_exceeded',
                        'retry_after': retry_after
                    },
                    wait=retry_after
                )
                
            return self.get_response(request)
            
        except Throttled as e:
            return Response(e.detail, status=429)
        except Exception as e:
            logger.error(
                'Rate limit middleware error',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return self.get_response(request)
        
    def _get_rate_limit_key(self, request: Request) -> str:
        """Get rate limit key for the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            str: Rate limit key or None if no limit applies
        """
        try:
            # Get endpoint name from URL
            path_parts = request.path.strip('/').split('/')
            if len(path_parts) < 3 or path_parts[0] != 'api':
                return None
                
            # Get rate limit from settings
            endpoint = path_parts[-1]
            if endpoint in self.rate_limits.get('auth', {}):
                limit = self.rate_limits['auth'][endpoint]
            else:
                limit = self.rate_limits['default']
                
            # Build key based on user/IP
            if request.user.is_authenticated:
                key = f'rate_limit:{limit}:user:{request.user.id}'
            else:
                key = f'rate_limit:{limit}:ip:{request.META.get("REMOTE_ADDR")}'
                
            return key
            
        except Exception as e:
            logger.error(
                'Error getting rate limit key',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return None
        
    def _check_rate_limit(self, key: str, request: Request) -> bool:
        """Check if request is within rate limit.
        
        Args:
            key: Rate limit key
            request: The HTTP request
            
        Returns:
            bool: True if within limit, False otherwise
        """
        try:
            # Parse rate limit
            limit, period = key.split(':')[1].split('/')
            limit = int(limit)
            
            # Get current count
            count = cache.get(key, 0)
            if count >= limit:
                return False
                
            # Increment count
            cache.set(key, count + 1, self._get_period_seconds(period))
            return True
            
        except Exception as e:
            logger.error(
                'Error checking rate limit',
                extra={
                    'error': str(e),
                    'key': key,
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return True  # Allow request on error
            
    def _get_period_seconds(self, period: str) -> int:
        """Convert period string to seconds.
        
        Args:
            period: Period string (e.g., 'hour', 'minute')
            
        Returns:
            int: Period in seconds
        """
        periods = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        return periods.get(period.lower(), 3600)  # Default to 1 hour
        
    def _get_retry_after(self, key: str) -> int:
        """Get seconds until rate limit resets.
        
        Args:
            key: Rate limit key
            
        Returns:
            int: Seconds until reset
        """
        try:
            ttl = cache.ttl(key)
            return max(ttl, 0) if ttl is not None else 0
        except Exception as e:
            logger.error(
                'Error getting retry after',
                extra={
                    'error': str(e),
                    'key': key
                },
                exc_info=True
            )
            return 0  # Default to immediate retry

class AuditLogMiddleware:
    """Middleware for audit logging API requests and responses.
    
    This middleware logs:
    - All API requests and responses
    - Authentication attempts
    - Rate limit violations
    - Error responses
    """
    
    def __init__(self, get_response: Callable):
        """Initialize middleware.
        
        Args:
            get_response: The next middleware in the chain
        """
        self.get_response = get_response
        
    def __call__(self, request: Request) -> Response:
        """Process the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            Response: The HTTP response
        """
        try:
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
            
        except Exception as e:
            logger.error(
                'Audit log middleware error',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return self.get_response(request)
        
    def _get_request_data(self, request: Request) -> dict:
        """Get request data for logging.
        
        Args:
            request: The HTTP request
            
        Returns:
            dict: Request data
        """
        try:
            data = {
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET.items()),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'timestamp': timezone.now().isoformat()
            }
            
            # Add request body for non-GET requests
            if request.method != 'GET':
                try:
                    data['body'] = request.data
                except:
                    data['body'] = None
                    
            return data
            
        except Exception as e:
            logger.error(
                'Error getting request data',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            return {}
        
    def _log_request(
        self,
        request: Request,
        response: Response,
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
        try:
            # Determine action based on path
            path_parts = request.path.strip('/').split('/')
            if len(path_parts) < 3:
                action = 'API_REQUEST'
            else:
                action = f"{path_parts[1].upper()}_{path_parts[2].upper()}"
                
            # Get response data
            try:
                response_data = response.data
            except:
                response_data = None
                
            # Create audit log entry
            AuditLog.objects.create(
                action=action,
                user=request.user if request.user.is_authenticated else None,
                details={
                    'request': request_data,
                    'response': {
                        'status_code': response.status_code,
                        'data': response_data
                    },
                    'duration': duration
                }
            )
            
            # Log errors
            if response.status_code >= 400:
                logger.error(
                    f'API Error: {action}',
                    extra={
                        'request': request_data,
                        'response': response_data,
                        'status_code': response.status_code,
                        'duration': duration
                    }
                )
                
        except Exception as e:
            logger.error(
                'Error logging request',
                extra={
                    'error': str(e),
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            ) 