"""AI agents for report prioritization and voice transcription.

This module provides AI agents that interact with OpenRouter API for:
- Report prioritization based on urgency and impact
- Voice message transcription
- Report categorization and tagging
- Sentiment analysis
- Error handling and retries with exponential backoff
- Result caching and storage

Example usage:
    # Prioritize reports
    reports = Report.objects.filter(status='pending')
    prioritized = prioritize_reports(reports)
    
    # Transcribe voice message
    with open('message.mp3', 'rb') as audio:
        text = transcribe_message(audio)
        
    # Analyze report sentiment
    sentiment = analyze_report_sentiment(report)
    
    # Categorize report
    categories = categorize_report(report)
"""

import os
import json
import logging
import time
import random
import requests
from functools import wraps
from typing import List, Dict, Any, Optional, Callable, TypeVar, Union
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import   AuditLog
from  reports.models import Report
from engagement.models import Message
from .utils import prioritize_report, transcribe_voice

logger = logging.getLogger(__name__)

# Type variables for decorators
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# OpenRouter API settings
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1'
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY and settings.DEBUG:
    OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY

# API request settings
API_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 60  # seconds
JITTER_FACTOR = 0.1  # Add randomness to retry delays

# Cache settings
CACHE_TIMEOUT = 3600  # 1 hour
PRIORITY_CACHE_KEY = 'report_priority_{report_id}'
TRANSCRIPT_CACHE_KEY = 'message_transcript_{message_id}'
SENTIMENT_CACHE_KEY = 'report_sentiment_{report_id}'
CATEGORY_CACHE_KEY = 'report_category_{report_id}'

class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""
    pass

class PrioritizationError(OpenRouterError):
    """Exception raised for report prioritization errors."""
    pass

class TranscriptionError(OpenRouterError):
    """Exception raised for voice transcription errors."""
    pass

class AIProcessingError(OpenRouterError):
    """Exception raised for general AI processing errors."""
    pass

class SentimentAnalysisError(OpenRouterError):
    """Exception raised for sentiment analysis errors."""
    pass

class CategorizationError(OpenRouterError):
    """Exception raised for report categorization errors."""
    pass

def with_retry(
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_RETRY_DELAY,
    max_delay: float = MAX_RETRY_DELAY,
    jitter: float = JITTER_FACTOR
) -> Callable[[F], F]:
    """Decorator for retrying API calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        jitter: Random jitter factor (0-1)
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, OpenRouterError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                        
                    # Calculate delay with exponential backoff and jitter
                    delay = min(delay * 2, max_delay)
                    jitter_amount = delay * jitter * random.uniform(-1, 1)
                    sleep_time = delay + jitter_amount
                    
                    logger.warning(
                        f'API call failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. '
                        f'Retrying in {sleep_time:.2f}s...'
                    )
                    time.sleep(sleep_time)
                    
            raise last_exception
            
        return wrapper
    return decorator

@with_retry()
def _call_openrouter_api(
    endpoint: str,
    method: str = 'POST',
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Make API call to OpenRouter with retry logic.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        headers: Request headers
        **kwargs: Additional request arguments
        
    Returns:
        Dict[str, Any]: API response data
        
    Raises:
        OpenRouterError: If API call fails
    """
    if headers is None:
        headers = {}
        
    headers.setdefault('Authorization', f'Bearer {OPENROUTER_API_KEY}')
    
    try:
        response = requests.request(
            method,
            f'{OPENROUTER_API_URL}/{endpoint}',
            headers=headers,
            timeout=API_TIMEOUT,
            **kwargs
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise OpenRouterError(f'OpenRouter API error: {str(e)}')

@with_retry()
def prioritize_reports(reports: List[Report]) -> List[Dict[str, Any]]:
    """Prioritize reports using OpenRouter AI.
    
    This function:
    1. Fetches cached priorities if available
    2. Calls OpenRouter API for uncached reports
    3. Updates report priorities in database
    4. Caches results for future use
    
    Args:
        reports: List of Report objects to prioritize
        
    Returns:
        List[Dict[str, Any]]: List of prioritized reports with scores:
            {
                'report_id': str,
                'priority_score': float,
                'urgency_level': str,
                'impact_score': float,
                'reasoning': str
            }
            
    Raises:
        PrioritizationError: If API call fails
        ValueError: If reports list is empty
    """
    if not reports:
        raise ValueError('Reports list cannot be empty')
        
    # Get cached priorities
    cached_results = {}
    uncached_reports = []
    
    for report in reports:
        cache_key = PRIORITY_CACHE_KEY.format(report_id=report.id)
        cached = cache.get(cache_key)
        if cached:
            cached_results[report.id] = cached
        else:
            uncached_reports.append(report)
            
    if not uncached_reports:
        return list(cached_results.values())
        
    # Prepare API request
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Prepare report data
    report_data = []
    for report in uncached_reports:
        report_data.append({
            'id': str(report.id),
            'title': report.title,
            'description': report.description,
            'category': report.category,
            'location': report.location,
            'created_at': report.created_at.isoformat(),
            'status': report.status,
            'upvotes': report.upvotes,
            'comments': report.comments.count()
        })
        
    # Call OpenRouter API
    try:
        response = requests.post(
            f'{OPENROUTER_API_URL}/prioritize',
            headers=headers,
            json={'reports': report_data},
            timeout=API_TIMEOUT
        )
        response.raise_for_status()
        
        # Process results
        results = response.json()['priorities']
        
        # Update database and cache
        with ThreadPoolExecutor() as executor:
            futures = []
            for result in results:
                report_id = result['report_id']
                cache_key = PRIORITY_CACHE_KEY.format(report_id=report_id)
                
                # Cache result
                cache.set(cache_key, result, CACHE_TIMEOUT)
                cached_results[report_id] = result
                
                # Update database
                futures.append(
                    executor.submit(
                        _update_report_priority,
                        report_id,
                        result
                    )
                )
                
            # Wait for all updates
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f'Failed to update report priority: {str(e)}')
                    
        # Log success
        AuditLog.objects.create(
            action='REPORT_PRIORITIZATION_SUCCESS',
            details={
                'report_count': len(reports),
                'cached_count': len(cached_results) - len(uncached_reports),
                'api_count': len(uncached_reports)
            }
        )
        
        return list(cached_results.values())
        
    except requests.RequestException as e:
        error_msg = f'OpenRouter API error: {str(e)}'
        logger.error(error_msg)
        
        # Log failure
        AuditLog.objects.create(
            action='REPORT_PRIORITIZATION_FAILED',
            details={
                'error': str(e),
                'report_count': len(reports)
            }
        )
        
        raise PrioritizationError(error_msg)
        
@with_retry()
def transcribe_message(audio_file: Any) -> str:
    """Transcribe voice message using OpenRouter AI.
    
    This function:
    1. Checks cache for existing transcript
    2. Calls OpenRouter API for transcription
    3. Stores transcript in database
    4. Caches result for future use
    
    Args:
        audio_file: File-like object containing audio data
        
    Returns:
        str: Transcribed text
        
    Raises:
        TranscriptionError: If API call fails
        ValueError: If audio file is invalid
    """
    if not audio_file:
        raise ValueError('Audio file is required')
        
    # Generate message ID from file hash
    message_id = _get_file_hash(audio_file)
    cache_key = TRANSCRIPT_CACHE_KEY.format(message_id=message_id)
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached
        
    # Prepare API request
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'audio/mpeg'  # Adjust based on file type
    }
    
    # Call OpenRouter API
    try:
        response = requests.post(
            f'{OPENROUTER_API_URL}/transcribe',
            headers=headers,
            data=audio_file,
            timeout=API_TIMEOUT
        )
        response.raise_for_status()
        
        # Get transcript
        transcript = response.json()['text']
        
        # Store in database
        try:
            Message.objects.create(
                message_id=message_id,
                content=transcript,
                content_type='text',
                source='voice',
                created_at=timezone.now()
            )
        except Exception as e:
            logger.error(f'Failed to store transcript: {str(e)}')
            
        # Cache result
        cache.set(cache_key, transcript, CACHE_TIMEOUT)
        
        # Log success
        AuditLog.objects.create(
            action='MESSAGE_TRANSCRIPTION_SUCCESS',
            details={
                'message_id': message_id,
                'length': len(transcript)
            }
        )
        
        return transcript
        
    except requests.RequestException as e:
        error_msg = f'OpenRouter API error: {str(e)}'
        logger.error(error_msg)
        
        # Log failure
        AuditLog.objects.create(
            action='MESSAGE_TRANSCRIPTION_FAILED',
            details={
                'error': str(e),
                'message_id': message_id
            }
        )
        
        raise TranscriptionError(error_msg)
        
@with_retry()
def analyze_report_sentiment(report: Report) -> Dict[str, Any]:
    """Analyze report sentiment using OpenRouter AI.
    
    This function:
    1. Checks cache for existing analysis
    2. Calls OpenRouter API for sentiment analysis
    3. Caches result for future use
    
    Args:
        report: Report object to analyze
        
    Returns:
        Dict[str, Any]: Sentiment analysis results:
            {
                'sentiment': str,  # 'positive', 'negative', 'neutral'
                'score': float,    # -1.0 to 1.0
                'confidence': float,  # 0.0 to 1.0
                'key_phrases': List[str],
                'emotions': Dict[str, float]
            }
            
    Raises:
        SentimentAnalysisError: If API call fails
    """
    cache_key = SENTIMENT_CACHE_KEY.format(report_id=report.id)
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached
        
    # Prepare request data
    data = {
        'text': f"{report.title}\n{report.description}",
        'include_phrases': True,
        'include_emotions': True
    }
    
    try:
        # Call API
        result = _call_openrouter_api(
            'analyze/sentiment',
            json=data
        )
        
        # Cache result
        cache.set(cache_key, result, CACHE_TIMEOUT)
        
        # Log success
        AuditLog.objects.create(
            action='SENTIMENT_ANALYSIS_SUCCESS',
            user=report.created_by,
            details={
                'report_id': str(report.id),
                'sentiment': result['sentiment'],
                'score': result['score']
            }
        )
        
        return result
        
    except OpenRouterError as e:
        # Log failure
        AuditLog.objects.create(
            action='SENTIMENT_ANALYSIS_FAILED',
            user=report.created_by,
            details={
                'report_id': str(report.id),
                'error': str(e)
            }
        )
        raise SentimentAnalysisError(str(e))

@with_retry()
def categorize_report(report: Report) -> Dict[str, Any]:
    """Categorize report using OpenRouter AI.
    
    This function:
    1. Checks cache for existing categories
    2. Calls OpenRouter API for categorization
    3. Caches result for future use
    
    Args:
        report: Report object to categorize
        
    Returns:
        Dict[str, Any]: Categorization results:
            {
                'primary_category': str,
                'categories': List[Dict[str, Any]],  # List of {category, confidence}
                'tags': List[str],
                'location_relevance': float,
                'urgency_indicators': List[str]
            }
            
    Raises:
        CategorizationError: If API call fails
    """
    cache_key = CATEGORY_CACHE_KEY.format(report_id=report.id)
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached
        
    # Prepare request data
    data = {
        'text': f"{report.title}\n{report.description}",
        'location': report.location,
        'include_tags': True,
        'include_urgency': True
    }
    
    try:
        # Call API
        result = _call_openrouter_api(
            'analyze/categorize',
            json=data
        )
        
        # Cache result
        cache.set(cache_key, result, CACHE_TIMEOUT)
        
        # Update report categories
        report.categories.set(result['categories'])
        report.tags.set(result['tags'])
        report.save()
        
        # Log success
        AuditLog.objects.create(
            action='REPORT_CATEGORIZATION_SUCCESS',
            user=report.created_by,
            details={
                'report_id': str(report.id),
                'primary_category': result['primary_category'],
                'category_count': len(result['categories'])
            }
        )
        
        return result
        
    except OpenRouterError as e:
        # Log failure
        AuditLog.objects.create(
            action='REPORT_CATEGORIZATION_FAILED',
            user=report.created_by,
            details={
                'report_id': str(report.id),
                'error': str(e)
            }
        )
        raise CategorizationError(str(e))

def _update_report_priority(report_id: str, priority_data: Dict[str, Any]) -> None:
    """Update report priority in database.
    
    Args:
        report_id: Report ID
        priority_data: Priority data from API
    """
    try:
        report = Report.objects.get(id=report_id)
        report.priority_score = priority_data['priority_score']
        report.urgency_level = priority_data['urgency_level']
        report.impact_score = priority_data['impact_score']
        report.priority_reasoning = priority_data['reasoning']
        report.prioritized_at = timezone.now()
        report.save()
    except Report.DoesNotExist:
        logger.error(f'Report not found: {report_id}')
    except Exception as e:
        logger.error(f'Failed to update report {report_id}: {str(e)}')
        
def _get_file_hash(file_obj: Any) -> str:
    """Generate hash for file object.
    
    Args:
        file_obj: File-like object
        
    Returns:
        str: File hash
    """
    import hashlib
    hash_md5 = hashlib.md5()
    for chunk in iter(lambda: file_obj.read(4096), b''):
        hash_md5.update(chunk)
    file_obj.seek(0)  # Reset file pointer
    return hash_md5.hexdigest() 