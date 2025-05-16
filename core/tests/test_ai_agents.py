"""Tests for AI agents.

This module contains tests for:
- Report prioritization
- Voice transcription
- Sentiment analysis
- Report categorization
- Retry logic
- Caching
"""

import json
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import APIException

from core.models import Report, Message, AuditLog
from core.ai_agents import (
    prioritize_reports,
    transcribe_message,
    analyze_report_sentiment,
    categorize_report,
    OpenRouterError,
    PrioritizationError,
    TranscriptionError,
    SentimentAnalysisError,
    CategorizationError,
    with_retry
)

class AIAgentsTestCase(TestCase):
    """Test case for AI agents."""
    
    def setUp(self):
        """Set up test data."""
        # Create test report
        self.report = Report.objects.create(
            title='Test Report',
            description='This is a test report description.',
            category='INFRASTRUCTURE',
            location='Abia State',
            status='pending',
            created_by=None  # Anonymous report
        )
        
        # Create test audio file
        self.audio_file = MagicMock()
        self.audio_file.read.return_value = b'test audio data'
        
        # Clear cache
        cache.clear()
        
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_prioritize_reports_success(self, mock_api):
        """Test successful report prioritization."""
        # Mock API response
        mock_api.return_value = {
            'priorities': [{
                'report_id': str(self.report.id),
                'priority_score': 0.8,
                'urgency_level': 'HIGH',
                'impact_score': 0.7,
                'reasoning': 'Test reasoning'
            }]
        }
        
        # Call function
        results = prioritize_reports([self.report])
        
        # Check results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['report_id'], str(self.report.id))
        self.assertEqual(results[0]['urgency_level'], 'HIGH')
        
        # Check cache
        cached = cache.get(f'report_priority_{self.report.id}')
        self.assertIsNotNone(cached)
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='REPORT_PRIORITIZATION_SUCCESS'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_prioritize_reports_failure(self, mock_api):
        """Test failed report prioritization."""
        # Mock API error
        mock_api.side_effect = OpenRouterError('API error')
        
        # Call function
        with self.assertRaises(PrioritizationError):
            prioritize_reports([self.report])
            
        # Check audit log
        log = AuditLog.objects.filter(
            action='REPORT_PRIORITIZATION_FAILED'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_transcribe_message_success(self, mock_api):
        """Test successful message transcription."""
        # Mock API response
        mock_api.return_value = {
            'text': 'This is a test transcription.'
        }
        
        # Call function
        text = transcribe_message(self.audio_file)
        
        # Check result
        self.assertEqual(text, 'This is a test transcription.')
        
        # Check cache
        message_id = 'd41d8cd98f00b204e9800998ecf8427e'  # MD5 of empty file
        cached = cache.get(f'message_transcript_{message_id}')
        self.assertIsNotNone(cached)
        
        # Check database
        message = Message.objects.filter(
            message_id=message_id
        ).first()
        self.assertIsNotNone(message)
        self.assertEqual(message.content, text)
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='MESSAGE_TRANSCRIPTION_SUCCESS'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_transcribe_message_failure(self, mock_api):
        """Test failed message transcription."""
        # Mock API error
        mock_api.side_effect = OpenRouterError('API error')
        
        # Call function
        with self.assertRaises(TranscriptionError):
            transcribe_message(self.audio_file)
            
        # Check audit log
        log = AuditLog.objects.filter(
            action='MESSAGE_TRANSCRIPTION_FAILED'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_analyze_sentiment_success(self, mock_api):
        """Test successful sentiment analysis."""
        # Mock API response
        mock_api.return_value = {
            'sentiment': 'positive',
            'score': 0.8,
            'confidence': 0.9,
            'key_phrases': ['test', 'positive'],
            'emotions': {'joy': 0.7, 'trust': 0.8}
        }
        
        # Call function
        result = analyze_report_sentiment(self.report)
        
        # Check result
        self.assertEqual(result['sentiment'], 'positive')
        self.assertEqual(result['score'], 0.8)
        
        # Check cache
        cached = cache.get(f'report_sentiment_{self.report.id}')
        self.assertIsNotNone(cached)
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='SENTIMENT_ANALYSIS_SUCCESS'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_analyze_sentiment_failure(self, mock_api):
        """Test failed sentiment analysis."""
        # Mock API error
        mock_api.side_effect = OpenRouterError('API error')
        
        # Call function
        with self.assertRaises(SentimentAnalysisError):
            analyze_report_sentiment(self.report)
            
        # Check audit log
        log = AuditLog.objects.filter(
            action='SENTIMENT_ANALYSIS_FAILED'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_categorize_report_success(self, mock_api):
        """Test successful report categorization."""
        # Mock API response
        mock_api.return_value = {
            'primary_category': 'INFRASTRUCTURE',
            'categories': [
                {'category': 'INFRASTRUCTURE', 'confidence': 0.9},
                {'category': 'ROADS', 'confidence': 0.8}
            ],
            'tags': ['road', 'repair', 'urgent'],
            'location_relevance': 0.9,
            'urgency_indicators': ['safety', 'access']
        }
        
        # Call function
        result = categorize_report(self.report)
        
        # Check result
        self.assertEqual(result['primary_category'], 'INFRASTRUCTURE')
        self.assertEqual(len(result['categories']), 2)
        
        # Check cache
        cached = cache.get(f'report_category_{self.report.id}')
        self.assertIsNotNone(cached)
        
        # Check database
        self.report.refresh_from_db()
        self.assertEqual(self.report.categories.count(), 2)
        self.assertEqual(self.report.tags.count(), 3)
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='REPORT_CATEGORIZATION_SUCCESS'
        ).first()
        self.assertIsNotNone(log)
        
    @patch('core.ai_agents._call_openrouter_api')
    def test_categorize_report_failure(self, mock_api):
        """Test failed report categorization."""
        # Mock API error
        mock_api.side_effect = OpenRouterError('API error')
        
        # Call function
        with self.assertRaises(CategorizationError):
            categorize_report(self.report)
            
        # Check audit log
        log = AuditLog.objects.filter(
            action='REPORT_CATEGORIZATION_FAILED'
        ).first()
        self.assertIsNotNone(log)
        
    def test_retry_decorator(self):
        """Test retry decorator with exponential backoff."""
        # Create function that fails twice then succeeds
        mock_func = MagicMock()
        mock_func.side_effect = [
            OpenRouterError('First error'),
            OpenRouterError('Second error'),
            'success'
        ]
        
        # Apply retry decorator
        decorated = with_retry(max_retries=2)(mock_func)
        
        # Call function
        result = decorated()
        
        # Check result
        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 3)
        
    def test_retry_decorator_max_retries(self):
        """Test retry decorator with max retries exceeded."""
        # Create function that always fails
        mock_func = MagicMock()
        mock_func.side_effect = OpenRouterError('API error')
        
        # Apply retry decorator
        decorated = with_retry(max_retries=2)(mock_func)
        
        # Call function
        with self.assertRaises(OpenRouterError):
            decorated()
            
        # Check call count
        self.assertEqual(mock_func.call_count, 3)  # Initial + 2 retries 