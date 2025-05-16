from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from unittest.mock import patch, MagicMock
import uuid
import json

from accounts.models import User, Reward, Kiosk, SyncLog
from core.models import Location

class NINVerificationTests(TestCase):
    """Test cases for NIN verification endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = reverse('accounts:verify-nin')
        self.valid_data = {
            'nin': '12345678901',
            'first_name': 'John',
            'last_name': 'Doe',
            'date_of_birth': '1990-01-01'
        }
        self.verify_me_response = {
            'verified': True,
            'email': 'john.doe@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone_number': '+2348012345678'
        }
    
    @patch('requests.post')
    def test_successful_verification(self, mock_post):
        """Test successful NIN verification."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: self.verify_me_response
        )
        
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
        
        # Verify user was created
        user = User.objects.get(email=self.verify_me_response['email'])
        self.assertTrue(user.is_nin_verified)
        self.assertEqual(user.nin_number, self.valid_data['nin'])
    
    @patch('requests.post')
    def test_failed_verification(self, mock_post):
        """Test failed NIN verification."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'verified': False}
        )
        
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_invalid_data(self):
        """Test verification with invalid data."""
        invalid_data = self.valid_data.copy()
        invalid_data['nin'] = '123'  # Invalid NIN length
        
        response = self.client.post(self.url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('requests.post')
    def test_rate_limiting(self, mock_post):
        """Test rate limiting for NIN verification."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: self.verify_me_response
        )
        
        # Make 6 requests (should exceed anonymous rate limit)
        for _ in range(6):
            response = self.client.post(self.url, self.valid_data)
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

class UserProfileTests(TestCase):
    """Test cases for user profile endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.url = reverse('accounts:user-profile')
    
    def test_get_profile_authenticated(self):
        """Test getting profile for authenticated user."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
    
    def test_get_profile_unauthenticated(self):
        """Test getting profile without authentication."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class RewardsTests(TestCase):
    """Test cases for rewards endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.url = reverse('accounts:user-rewards')
        
        # Create some rewards
        self.rewards = [
            Reward.objects.create(
                user=self.user,
                reward_type='referral',
                reward_amount=100.00,
                description='Referral bonus'
            ),
            Reward.objects.create(
                user=self.user,
                reward_type='transaction',
                reward_amount=50.00,
                description='Transaction bonus',
                is_redeemed=True
            )
        ]
    
    def test_list_rewards_authenticated(self):
        """Test listing rewards for authenticated user."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_rewards(self):
        """Test filtering rewards."""
        self.client.force_authenticate(user=self.user)
        
        # Test filtering by redemption status
        response = self.client.get(f"{self.url}?is_redeemed=true")
        self.assertEqual(len(response.data), 1)
        
        # Test filtering by reward type
        response = self.client.get(f"{self.url}?reward_type=referral")
        self.assertEqual(len(response.data), 1)

class KioskTests(TestCase):
    """Test cases for kiosk endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.location = Location.objects.create(
            name='Test Location',
            type='lga'
        )
        self.operator = User.objects.create_user(
            email='operator@example.com',
            password='testpass123',
            is_kiosk_operator=True
        )
        self.kiosk = Kiosk.objects.create(
            name='Test Kiosk',
            location=self.location,
            operator=self.operator,
            is_active=True
        )
        self.list_url = reverse('accounts:list-kiosks')
        self.sync_url = reverse('accounts:create-sync-log')
    
    def test_list_kiosks(self):
        """Test listing kiosks."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_kiosks(self):
        """Test filtering kiosks."""
        # Test filtering by location
        response = self.client.get(f"{self.list_url}?location_id={self.location.id}")
        self.assertEqual(len(response.data), 1)
        
        # Test filtering by active status
        response = self.client.get(f"{self.list_url}?is_active=true")
        self.assertEqual(len(response.data), 1)
    
    def test_create_sync_log_authenticated(self):
        """Test creating sync log as kiosk operator."""
        self.client.force_authenticate(user=self.operator)
        data = {
            'sync_type': 'full',
            'sync_started_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.sync_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['syncType'], 'full')
        
        # Verify kiosk last sync time was updated
        self.kiosk.refresh_from_db()
        self.assertIsNotNone(self.kiosk.last_sync_at)
    
    def test_create_sync_log_unauthenticated(self):
        """Test creating sync log without authentication."""
        data = {
            'sync_type': 'full',
            'sync_started_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.sync_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_sync_log_non_operator(self):
        """Test creating sync log as non-operator."""
        non_operator = User.objects.create_user(
            email='non.operator@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=non_operator)
        
        data = {
            'sync_type': 'full',
            'sync_started_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.sync_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cache_invalidation(self):
        """Test that kiosk cache is invalidated after sync."""
        # First request should cache the results
        response1 = self.client.get(self.list_url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Create a sync log
        self.client.force_authenticate(user=self.operator)
        data = {
            'sync_type': 'full',
            'sync_started_at': timezone.now().isoformat()
        }
        self.client.post(self.sync_url, data)
        
        # Second request should get fresh data
        response2 = self.client.get(self.list_url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response1.data, response2.data) 