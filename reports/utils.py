"""Utility functions for the reports app."""

import re
import html
from typing import Optional, Dict, Any, List, Tuple
import os
import json
import requests
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from django.conf import settings
# from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import httpx
import logging
import uuid
from datetime import datetime, timedelta
from django.core.files.storage import default_storage
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate
from asgiref.sync import sync_to_async
import phonenumbers
from .models import Report, ReportComment, AuditLog

logger = logging.getLogger(__name__)

def sanitize_text(text: str) -> str:
    """Sanitize text input to prevent XSS and other injection attacks.
    
    Args:
        text: Raw text input from user
        
    Returns:
        Sanitized text safe for storage and display
    """
    if not text:
        return ""
        
    # Convert HTML entities to their unicode equivalents
    text = html.unescape(text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove null bytes and other control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text

def extract_exif_location(image_path: str) -> Optional[tuple[float, float]]:
    """Extract GPS coordinates from image EXIF data if available.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (latitude, longitude) if GPS data found, None otherwise
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        
        image = Image.open(image_path)
        exif = image._getexif()
        
        if not exif:
            return None
            
        gps_info = {}
        
        for tag_id in exif:
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
                for gps_tag in exif[tag_id]:
                    sub_tag = GPSTAGS.get(gps_tag, gps_tag)
                    gps_info[sub_tag] = exif[tag_id][gps_tag]
                    
        if not gps_info:
            return None
            
        lat = gps_info.get('GPSLatitude')
        lat_ref = gps_info.get('GPSLatitudeRef')
        lon = gps_info.get('GPSLongitude') 
        lon_ref = gps_info.get('GPSLongitudeRef')
        
        if not all([lat, lat_ref, lon, lon_ref]):
            return None
            
        def convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
            
        latitude = convert_to_degrees(lat)
        if lat_ref != 'N':
            latitude = -latitude
            
        longitude = convert_to_degrees(lon)
        if lon_ref != 'E':
            longitude = -longitude
            
        return (latitude, longitude)
        
    except Exception as e:
        logger.error(f'Error extracting EXIF data: {str(e)}')
        return None 

# def extract_location_from_exif(image_file) -> Optional[Point]:
#     """Extract GPS coordinates from image EXIF data.
    
#     Args:
#         image_file: Image file object
        
#     Returns:
#         Point object with coordinates or None
#     """
#     try:
#         image = Image.open(image_file)
#         exif = image._getexif()
        
#         if not exif:
#             return None
            
#         # Get EXIF tags
#         gps_info = {}
#         for tag, value in exif.items():
#             decoded = TAGS.get(tag, tag)
#             if decoded == 'GPSInfo':
#                 for gps_tag in value:
#                     sub_decoded = GPSTAGS.get(gps_tag, gps_tag)
#                     gps_info[sub_decoded] = value[gps_tag]
        
#         if not gps_info:
#             return None
            
#         # Extract latitude
#         lat_dms = gps_info.get('GPSLatitude')
#         lat_ref = gps_info.get('GPSLatitudeRef')
        
#         if not lat_dms or not lat_ref:
#             return None
            
#         lat = lat_dms[0] + lat_dms[1]/60 + lat_dms[2]/3600
#         if lat_ref == 'S':
#             lat = -lat
            
#         # Extract longitude
#         lon_dms = gps_info.get('GPSLongitude')
#         lon_ref = gps_info.get('GPSLongitudeRef')
        
#         if not lon_dms or not lon_ref:
#             return None
            
#         lon = lon_dms[0] + lon_dms[1]/60 + lon_dms[2]/3600
#         if lon_ref == 'W':
#             lon = -lon
            
#         return Point(lon, lat)
        
#     except Exception as e:
#         logger.error(f'Error extracting EXIF data: {str(e)}')
#         return None

def _convert_to_degrees(value):
    """Helper function to convert GPS coordinates to decimal degrees."""
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)

async def generate_ai_summary(text):
    """Generate an AI summary of the report text using OpenRouter API.
    
    Args:
        text (str): The report text to summarize
        
    Returns:
        str: AI-generated summary or None if generation fails
    """
    if not settings.ENABLE_AI_PROCESSING or not settings.OPENROUTER_API_KEY:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'mistral/mistral-7b',
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are a helpful assistant that summarizes citizen reports.'
                        },
                        {
                            'role': 'user',
                            'content': f'Please provide a concise summary of this citizen report: {text}'
                        }
                    ],
                    'max_tokens': 150
                }
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()

    except Exception as e:
        logger.error(f"Failed to generate AI summary: {str(e)}")
        return None

async def calculate_ai_priority(text):
    """Calculate priority score using AI analysis.
    
    Args:
        text (str): The report text to analyze
        
    Returns:
        float: Priority score between 0 and 1, or None if calculation fails
    """
    if not settings.ENABLE_AI_PROCESSING or not settings.OPENROUTER_API_KEY:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'mistral/mistral-7b',
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are an AI that assesses the urgency of citizen reports. Respond only with a number between 0 and 1, where 1 is most urgent.'
                        },
                        {
                            'role': 'user',
                            'content': f'Rate the urgency of this report: {text}'
                        }
                    ],
                    'max_tokens': 10
                }
            )
            response.raise_for_status()
            score_text = response.json()['choices'][0]['message']['content'].strip()
            return float(score_text)

    except Exception as e:
        logger.error(f"Failed to calculate AI priority: {str(e)}")
        return None

def validate_file_extension(file, allowed_extensions: List[str]) -> bool:
    """Validate file extension.
    
    Args:
        file: File object to validate
        allowed_extensions: List of allowed extensions
        
    Returns:
        True if valid, False otherwise
    """
    ext = os.path.splitext(file.name)[1][1:].lower()
    return ext in allowed_extensions

def get_file_upload_path(file, folder: str) -> str:
    """Generate upload path for file.
    
    Args:
        file: File object
        folder: Target folder name
        
    Returns:
        Upload path
    """
    ext = os.path.splitext(file.name)[1]
    filename = f'{uuid.uuid4()}{ext}'
    return os.path.join('reports', folder, filename)

def sanitize_phone_number(phone: str) -> Optional[str]:
    """Sanitize and validate phone number.
    
    Args:
        phone: Phone number to sanitize
        
    Returns:
        Sanitized phone number or None if invalid
    """
    try:
        # Parse phone number
        parsed = phonenumbers.parse(phone, 'NG')
        
        # Check if valid
        if not phonenumbers.is_valid_number(parsed):
            return None
            
        # Format to international format
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164
        )
        
    except Exception as e:
        logger.error(f'Phone number validation error: {str(e)}')
        return None

async def translate_text(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Translate text between languages.
    
    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Translated text or None on error
    """
    try:
        # Check cache first
        cache_key = f'translation:{source_lang}:{target_lang}:{hash(text)}'
        cached = cache.get(cache_key)
        if cached:
            return cached
            
        # Call OpenRouter translation API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/translate',
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'text': text,
                    'source_lang': source_lang,
                    'target_lang': target_lang
                }
            )
            
            if response.status_code == 200:
                translation = response.json()['translation']
                
                # Cache for 24 hours
                cache.set(cache_key, translation, 60 * 60 * 24)
                
                return translation
                
            return None
            
    except Exception as e:
        logger.error(f'Translation error: {str(e)}')
        return None

def get_report_statistics(
    start_date: datetime,
    end_date: datetime,
    lga=None
) -> Dict[str, Any]:
    """Get report statistics.
    
    Args:
        start_date: Start date for statistics
        end_date: End date for statistics
        lga: Optional LGA to filter by
        
    Returns:
        Dictionary of statistics
    """
    # Base queryset
    queryset = Report.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Filter by LGA if specified
    if lga:
        queryset = queryset.filter(lga=lga)
    
    # Get total reports
    total_reports = queryset.count()
    
    # Get reports by status
    reports_by_status = dict(
        queryset.values('status')
        .annotate(count=Count('id'))
        .values_list('status', 'count')
    )
    
    # Get reports by category
    reports_by_category = dict(
        queryset.values('category')
        .annotate(count=Count('id'))
        .values_list('category', 'count')
    )
    
    # Get reports by priority
    reports_by_priority = dict(
        queryset.values('priority')
        .annotate(count=Count('id'))
        .values_list('priority', 'count')
    )
    
    # Get average resolution time
    resolved = queryset.filter(
        status='RESOLVED',
        resolved_at__isnull=False
    )
    avg_resolution_time = resolved.aggregate(
        avg=Avg('resolved_at' - 'created_at')
    )['avg']
    
    # Get reports over time
    reports_over_time = list(
        queryset.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
        .values('date', 'count')
    )
    
    return {
        'total_reports': total_reports,
        'reports_by_status': reports_by_status,
        'reports_by_category': reports_by_category,
        'reports_by_priority': reports_by_priority,
        'average_resolution_time': avg_resolution_time,
        'reports_over_time': reports_over_time
    }

def get_similar_reports(report: Report) -> List[Report]:
    """Get similar reports.
    
    Args:
        report: Report to find similar reports for
        
    Returns:
        List of similar reports
    """
    # Get reports in same LGA and category from last 30 days
    similar = Report.objects.filter(
        lga=report.lga,
        category=report.category,
        created_at__gte=timezone.now() - timedelta(days=30)
    ).exclude(
        id=report.id
    )
    
    # Add text similarity if AI enabled
    if settings.ENABLE_AI_PROCESSING:
        from .integrations.openrouter import OpenRouterAI
        
        ai_client = OpenRouterAI()
        embeddings = ai_client.get_embeddings([
            report.title + ' ' + report.description
            for report in similar
        ])
        
        if embeddings:
            # Sort by cosine similarity
            target_embedding = embeddings[0]
            similarities = [
                (report, ai_client.cosine_similarity(target_embedding, emb))
                for report, emb in zip(similar, embeddings[1:])
            ]
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            return [report for report, _ in similarities[:5]]
    
    # Fallback to simple filtering
    return similar[:5]

async def notify_officials(report: Report, officials: Optional[List] = None):
    """Notify officials about a report.
    
    Args:
        report: Report to notify about
        officials: Optional list of specific officials to notify
    """
    try:
        from .integrations.africas_talking import AfricasTalkingClient
        
        # Get officials to notify
        if not officials:
            officials = []
            
            # Add LGA officials
            if report.lga:
                officials.extend(
                    User.objects.filter(
                        is_active=True,
                        is_lga_official=True,
                        lga=report.lga
                    )
                )
            
            # Add state officials
            officials.extend(
                User.objects.filter(
                    is_active=True,
                    is_state_official=True
                )
            )
        
        # Send notifications
        sms_client = AfricasTalkingClient()
        
        for official in officials:
            if official.phone:
                message = (
                    f'New report: {report.title}\n'
                    f'Category: {report.get_category_display()}\n'
                    f'Priority: {report.get_priority_display()}\n'
                    f'Location: {report.address}\n'
                    f'View at: {settings.SITE_URL}/reports/{report.id}'
                )
                
                await sms_client.send_sms(
                    to=official.phone,
                    message=message
                )
                
    except Exception as e:
        logger.error(f'Error notifying officials: {str(e)}')

async def notify_reporter(report: Report):
    """Notify reporter about their report.
    
    Args:
        report: Report to notify about
    """
    try:
        from .integrations.africas_talking import AfricasTalkingClient
        
        if report.reporter and report.reporter.phone:
            sms_client = AfricasTalkingClient()
            
            message = (
                f'Thank you for your report: {report.title}\n'
                f'Reference ID: {report.id}\n'
                f'Status: {report.get_status_display()}\n'
                f'Track at: {settings.SITE_URL}/reports/{report.id}'
            )
            
            await sms_client.send_sms(
                to=report.reporter.phone,
                message=message
            )
            
    except Exception as e:
        logger.error(f'Error notifying reporter: {str(e)}') 