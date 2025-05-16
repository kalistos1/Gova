"""Base service class with common functionality."""

import logging
from typing import Any, Dict, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class BaseService:
    """Base class for all services with common functionality."""
    
    def __init__(self):
        """Initialize base service."""
        self.cache = cache
        
    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling and logging.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Optional request headers
            data: Optional request data
            timeout: Request timeout in seconds
            
        Returns:
            Dict containing response data or error
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=data,
                    timeout=timeout
                ) as response:
                    response.raise_for_status()
                    return await response.json()
                    
        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {str(e)}")
            return {
                'status': 'error',
                'message': f"Request failed: {str(e)}"
            }
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                'status': 'error',
                'message': f"Unexpected error: {str(e)}"
            }
            
    def _get_cached(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """Get value from cache with logging.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            value = self.cache.get(key, default)
            if value is not None:
                logger.debug(f"Cache hit for key: {key}")
            else:
                logger.debug(f"Cache miss for key: {key}")
            return value
            
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {str(e)}")
            return default
            
    def _set_cached(
        self,
        key: str,
        value: Any,
        timeout: Optional[int] = None
    ) -> bool:
        """Set value in cache with logging.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Optional cache timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.cache.set(key, value, timeout)
            logger.debug(f"Cached value for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {str(e)}")
            return False
            
    def _format_phone(
        self,
        phone: str,
        country_code: str = '234'
    ) -> str:
        """Format phone number to standard format.
        
        Args:
            phone: Phone number string
            country_code: Country code (default: Nigeria)
            
        Returns:
            Formatted phone number
        """
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Remove leading zeros
        phone = phone.lstrip('0')
        
        # Add country code if not present
        if not phone.startswith(country_code):
            phone = f"{country_code}{phone}"
            
        return phone
        
    def _validate_nin(self, nin: str) -> bool:
        """Validate NIN format.
        
        Args:
            nin: NIN string
            
        Returns:
            True if valid format, False otherwise
        """
        # Remove any non-digit characters
        nin = ''.join(filter(str.isdigit, nin))
        
        # Check length (11 digits)
        if len(nin) != 11:
            return False
            
        # Add additional validation rules as needed
        return True 