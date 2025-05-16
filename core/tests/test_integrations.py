"""Integration tests for external services."""

import os
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.conf import settings
from core.ai_agents import prioritize_reports, transcribe_message
from core.models import Report, Message
from core.services import (
    verify_nin,
    process_payment,
    send_sms,
    send_ussd,
    track_grant,
    send_whatsapp
)

class OpenRouterIntegrationTests(TestCase):
    """Test OpenRouter AI integration."""
    
    def setUp(self):
        self.report = Report.objects.create(
            title="Test Report",
            description="This is a test report about a pothole",
            location="Aba",
            category="infrastructure"
        )
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_report_prioritization(self, mock_api):
        """Test report prioritization with OpenRouter."""
        mock_api.return_value = {
            'priority_score': 0.8,
            'urgency_level': 'high',
            'impact_score': 0.7,
            'reasoning': 'Critical infrastructure issue'
        }
        
        result = prioritize_reports([self.report])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['urgency_level'], 'high')
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_voice_transcription(self, mock_api):
        """Test voice message transcription."""
        mock_api.return_value = {
            'text': 'This is a test voice message'
        }
        
        with open('test_audio.mp3', 'wb') as f:
            f.write(b'test audio content')
            
        with open('test_audio.mp3', 'rb') as audio:
            text = transcribe_message(audio)
            self.assertEqual(text, 'This is a test voice message')
            
class VerifyMeIntegrationTests(TestCase):
    """Test VerifyMe NIN verification."""
    
    @patch('core.services.requests.post')
    def test_nin_verification(self, mock_post):
        """Test NIN verification."""
        mock_post.return_value.json.return_value = {
            'status': 'success',
            'verified': True,
            'data': {
                'nin': '12345678901',
                'firstName': 'John',
                'lastName': 'Doe'
            }
        }
        
        result = verify_nin('12345678901')
        self.assertTrue(result['verified'])
        
class FlutterwaveIntegrationTests(TestCase):
    """Test Flutterwave payment integration."""
    
    @patch('core.services.requests.post')
    def test_payment_processing(self, mock_post):
        """Test payment processing."""
        mock_post.return_value.json.return_value = {
            'status': 'success',
            'data': {
                'tx_ref': 'test_tx_123',
                'amount': 1000,
                'currency': 'NGN',
                'status': 'successful'
            }
        }
        
        result = process_payment(
            amount=1000,
            email='test@example.com',
            reference='test_tx_123'
        )
        self.assertEqual(result['status'], 'successful')
        
class AfricasTalkingIntegrationTests(TestCase):
    """Test Africa's Talking integration."""
    
    @patch('core.services.africastalking.SMS')
    def test_sms_sending(self, mock_sms):
        """Test SMS sending."""
        mock_sms.send.return_value = {
            'SMSMessageData': {
                'Recipients': [{
                    'number': '+2348012345678',
                    'status': 'Success',
                    'messageId': 'test_id_123'
                }]
            }
        }
        
        result = send_sms(
            phone='+2348012345678',
            message='Test SMS'
        )
        self.assertEqual(result['status'], 'Success')
        
    @patch('core.services.africastalking.USSD')
    def test_ussd_session(self, mock_ussd):
        """Test USSD session."""
        mock_ussd.return_value = {
            'status': 'Success',
            'sessionId': 'test_session_123',
            'message': 'Welcome to AbiaHub'
        }
        
        result = send_ussd(
            phone='+2348012345678',
            session_id='test_session_123',
            text='*384*1#'
        )
        self.assertEqual(result['status'], 'Success')
        
class StellarIntegrationTests(TestCase):
    """Test Stellar blockchain integration."""
    
    @patch('core.services.Server')
    def test_grant_tracking(self, mock_server):
        """Test grant tracking on Stellar."""
        mock_transaction = MagicMock()
        mock_transaction.hash = 'test_hash_123'
        mock_server.transactions.return_value = mock_transaction
        
        result = track_grant(
            amount=1000,
            recipient='test_recipient',
            grant_id='test_grant_123'
        )
        self.assertEqual(result['hash'], 'test_hash_123')
        
class AiSensyIntegrationTests(TestCase):
    """Test AiSensy WhatsApp integration."""
    
    @patch('core.services.requests.post')
    def test_whatsapp_sending(self, mock_post):
        """Test WhatsApp message sending."""
        mock_post.return_value.json.return_value = {
            'status': 'success',
            'message_id': 'test_msg_123'
        }
        
        result = send_whatsapp(
            phone='2348012345678',
            message='Test WhatsApp message'
        )
        self.assertEqual(result['status'], 'success')
        
if __name__ == '__main__':
    unittest.main() 