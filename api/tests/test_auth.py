"""Tests for authentication endpoints.

This module contains tests for:
- NIN verification
- JWT token management
- Password management
- Session management
"""

import json
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from core.models import AuditLog
from core.utils import verify_nin

class AuthenticationTestCase(TestCase):
    """Test case for authentication endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.nin_verify_url = reverse('api:nin-verify')
        self.token_refresh_url = reverse('api:token-refresh')
        self.token_verify_url = reverse('api:token-verify')
        self.token_blacklist_url = reverse('api:token-blacklist')
        self.password_reset_url = reverse('api:password-reset-request')
        self.password_reset_confirm_url = reverse('api:password-reset-confirm')
        self.password_change_url = reverse('api:password-change')
        self.logout_url = reverse('api:logout')
        
        # Test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            nin='12345678901',
            phone_number='+2348012345678',
            full_name='Test User'
        )
        
        # Test tokens
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh_token.access_token)
        
        # Clear cache
        cache.clear()
        
    def test_nin_verification_success(self):
        """Test successful NIN verification."""
        # Mock verify_nin response
        def mock_verify_nin(*args, **kwargs):
            return {
                'isVerified': True,
                'fullName': 'Test User',
                'dateOfBirth': '1990-01-01',
                'gender': 'M'
            }
            
        # Patch verify_nin function
        original_verify_nin = verify_nin
        verify_nin = mock_verify_nin
        
        try:
            # Make request
            data = {
                'nin': '12345678901',
                'phone': '+2348012345678'
            }
            response = self.client.post(
                self.nin_verify_url,
                data=json.dumps(data),
                content_type='application/json'
            )
            
            # Check response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('accessToken', response.data)
            self.assertIn('refreshToken', response.data)
            self.assertIn('user', response.data)
            
            # Check user creation
            user = User.objects.get(nin='12345678901')
            self.assertEqual(user.phone_number, '+2348012345678')
            self.assertEqual(user.full_name, 'Test User')
            self.assertTrue(user.is_nin_verified)
            
            # Check audit log
            log = AuditLog.objects.filter(
                action='NIN_VERIFICATION_SUCCESS',
                user=user
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.details['nin'], '12345678901')
            
        finally:
            # Restore original function
            verify_nin = original_verify_nin
            
    def test_nin_verification_failure(self):
        """Test failed NIN verification."""
        # Mock verify_nin response
        def mock_verify_nin(*args, **kwargs):
            return {
                'isVerified': False,
                'reason': 'Invalid NIN'
            }
            
        # Patch verify_nin function
        original_verify_nin = verify_nin
        verify_nin = mock_verify_nin
        
        try:
            # Make request
            data = {
                'nin': '12345678901',
                'phone': '+2348012345678'
            }
            response = self.client.post(
                self.nin_verify_url,
                data=json.dumps(data),
                content_type='application/json'
            )
            
            # Check response
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data['code'], 'verification_failed')
            
            # Check audit log
            log = AuditLog.objects.filter(
                action='NIN_VERIFICATION_FAILED'
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.details['nin'], '12345678901')
            
        finally:
            # Restore original function
            verify_nin = original_verify_nin
            
    def test_nin_verification_rate_limit(self):
        """Test NIN verification rate limiting."""
        # Make multiple requests
        data = {
            'nin': '12345678901',
            'phone': '+2348012345678'
        }
        
        for _ in range(6):  # Exceed 5/hour limit
            response = self.client.post(
                self.nin_verify_url,
                data=json.dumps(data),
                content_type='application/json'
            )
            
        # Check rate limit response
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['code'], 'rate_limit_exceeded')
        self.assertIn('retry_after', response.data)
        
    def test_token_refresh_success(self):
        """Test successful token refresh."""
        # Make request
        data = {
            'refresh': str(self.refresh_token)
        }
        response = self.client.post(
            self.token_refresh_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='TOKEN_REFRESHED',
            user=self.user
        ).first()
        self.assertIsNotNone(log)
        
    def test_token_refresh_failure(self):
        """Test failed token refresh."""
        # Make request with invalid token
        data = {
            'refresh': 'invalid.token.here'
        }
        response = self.client.post(
            self.token_refresh_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['code'], 'invalid_token')
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='TOKEN_REFRESH_FAILED'
        ).first()
        self.assertIsNotNone(log)
        
    def test_token_blacklist(self):
        """Test token blacklisting."""
        # Make request
        data = {
            'refresh': str(self.refresh_token)
        }
        response = self.client.post(
            self.token_blacklist_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to refresh blacklisted token
        response = self.client.post(
            self.token_refresh_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_password_reset_flow(self):
        """Test password reset flow."""
        # Request password reset
        data = {
            'email': self.user.email
        }
        response = self.client.post(
            self.password_reset_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get reset token from email (mocked)
        reset_token = 'test.reset.token'
        
        # Confirm password reset
        data = {
            'token': reset_token,
            'password': 'newpass123'
        }
        response = self.client.post(
            self.password_reset_confirm_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to login with new password
        self.assertTrue(
            self.client.login(
                email=self.user.email,
                password='newpass123'
            )
        )
        
    def test_password_change(self):
        """Test password change."""
        # Login
        self.client.force_authenticate(user=self.user)
        
        # Change password
        data = {
            'old_password': 'testpass123',
            'new_password': 'newpass123'
        }
        response = self.client.post(
            self.password_change_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to login with new password
        self.assertTrue(
            self.client.login(
                email=self.user.email,
                password='newpass123'
            )
        )
        
    def test_logout(self):
        """Test logout."""
        # Login
        self.client.force_authenticate(user=self.user)
        
        # Logout
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to access protected endpoint
        response = self.client.get(reverse('api:user-profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) 