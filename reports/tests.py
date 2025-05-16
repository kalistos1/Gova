from django.test import TestCase

# Create your tests here.

"""Tests for the reports app."""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
# from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock
import json
import uuid
from datetime import datetime, timedelta

from .models import Report, AuditLog
from .serializers import ReportSerializer
from core.models import LGA

User = get_user_model()

class ReportModelTests(TestCase):
    """Test cases for the Report model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            nin_verified=True
        )
        self.lga = LGA.objects.create(
            name='Test LGA',
            state='Abia',
            location=Point(7.0, 5.0)
        )
        self.report = Report.objects.create(
            title='Test Report',
            description='This is a test report description that meets the minimum length requirement.',
            category='INFRASTRUCTURE',
            location=Point(7.0, 5.0),
            address='123 Test Street',
            lga=self.lga,
            reporter=self.user
        )
        
    def test_report_creation(self):
        """Test creating a new report."""
        self.assertEqual(self.report.title, 'Test Report')
        self.assertEqual(self.report.status, 'PENDING')
        self.assertEqual(self.report.priority, 'MEDIUM')
        self.assertFalse(self.report.is_anonymous)
        
    def test_report_str_representation(self):
        """Test string representation of Report."""
        expected = f'Test Report (Pending Review)'
        self.assertEqual(str(self.report), expected)
        
    def test_anonymous_report(self):
        """Test creating an anonymous report."""
        anon_report = Report.objects.create(
            title='Anonymous Report',
            description='This is an anonymous report description that meets the minimum length.',
            category='SECURITY',
            location=Point(7.0, 5.0),
            address='456 Test Street',
            lga=self.lga,
            is_anonymous=True
        )
        self.assertIsNone(anon_report.reporter)
        
class ReportAPITests(APITestCase):
    """Test cases for the Report API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            nin_verified=True
        )
        self.lga = LGA.objects.create(
            name='Test LGA',
            state='Abia',
            location=Point(7.0, 5.0)
        )
        self.report_data = {
            'title': 'API Test Report',
            'description': 'This is a test report submitted through the API.',
            'category': 'INFRASTRUCTURE',
            'location': {'type': 'Point', 'coordinates': [7.0, 5.0]},
            'address': '789 API Street',
            'lga': self.lga.id
        }
        self.client.force_authenticate(user=self.user)
        
    def test_create_report(self):
        """Test creating a report through the API."""
        url = reverse('reports:report-list')
        response = self.client.post(url, self.report_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(Report.objects.get().title, 'API Test Report')
        
    def test_create_report_with_image(self):
        """Test creating a report with an image."""
        url = reverse('reports:report-list')
        image = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        data = self.report_data.copy()
        data['image'] = image
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
    @patch('reports.views.get_ai_priority')
    def test_create_report_with_ai_analysis(self, mock_ai):
        """Test AI analysis during report creation."""
        mock_ai.return_value = ('HIGH', 'AI generated summary')
        url = reverse('reports:report-list')
        response = self.client.post(url, self.report_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['priority'], 'HIGH')
        self.assertEqual(response.data['ai_summary'], 'AI generated summary')
        
    def test_list_reports(self):
        """Test listing reports."""
        Report.objects.create(
            title='Report 1',
            description='Description 1 that meets minimum length requirement.',
            category='INFRASTRUCTURE',
            location=Point(7.0, 5.0),
            address='Address 1',
            lga=self.lga,
            reporter=self.user
        )
        Report.objects.create(
            title='Report 2',
            description='Description 2 that meets minimum length requirement.',
            category='SECURITY',
            location=Point(7.0, 5.0),
            address='Address 2',
            lga=self.lga,
            reporter=self.user
        )
        url = reverse('reports:report-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_filter_reports(self):
        """Test filtering reports."""
        Report.objects.create(
            title='Infrastructure Report',
            description='Description that meets minimum length requirement.',
            category='INFRASTRUCTURE',
            location=Point(7.0, 5.0),
            address='Address 1',
            lga=self.lga,
            reporter=self.user
        )
        Report.objects.create(
            title='Security Report',
            description='Description that meets minimum length requirement.',
            category='SECURITY',
            location=Point(7.0, 5.0),
            address='Address 2',
            lga=self.lga,
            reporter=self.user
        )
        url = reverse('reports:report-list')
        response = self.client.get(url, {'category': 'INFRASTRUCTURE'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['category'],
            'INFRASTRUCTURE'
        )
        
class AuditLogTests(TestCase):
    """Test cases for the AuditLog functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.lga = LGA.objects.create(
            name='Test LGA',
            state='Abia',
            location=Point(7.0, 5.0)
        )
        self.report = Report.objects.create(
            title='Test Report',
            description='Description that meets minimum length requirement.',
            category='INFRASTRUCTURE',
            location=Point(7.0, 5.0),
            address='123 Test Street',
            lga=self.lga,
            reporter=self.user
        )
        
    def test_audit_log_creation(self):
        """Test creating an audit log entry."""
        log = AuditLog.objects.create(
            report=self.report,
            user=self.user,
            action='status_change',
            old_value={'status': 'PENDING'},
            new_value={'status': 'IN_PROGRESS'}
        )
        self.assertEqual(log.action, 'status_change')
        self.assertEqual(log.report, self.report)
        self.assertEqual(log.user, self.user)
        
    def test_audit_log_str_representation(self):
        """Test string representation of AuditLog."""
        log = AuditLog.objects.create(
            report=self.report,
            user=self.user,
            action='status_change'
        )
        expected = f'status_change on {self.report} by {self.user}'
        self.assertEqual(str(log), expected)
