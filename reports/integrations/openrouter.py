"""OpenRouter AI integration for report analysis and prioritization."""

import httpx
from django.conf import settings
from django.core.cache import cache
from typing import Dict, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)

class OpenRouterAI:
    """OpenRouter AI client for report analysis."""

    BASE_URL = "https://openrouter.ai/api/v1"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        """Initialize the OpenRouter AI client."""
        self.api_key = settings.OPENROUTER_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def analyze_report(self, report_text: str) -> Tuple[str, str]:
        """Analyze report text to determine priority and generate summary.
        
        Args:
            report_text (str): The report text to analyze
            
        Returns:
            Tuple[str, str]: Priority level and AI-generated summary
        """
        cache_key = f"report_analysis_{hash(report_text)}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result['priority'], cached_result['summary']

        try:
            async with httpx.AsyncClient() as client:
                # First, analyze priority
                priority_response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "llama2-70b",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an AI assistant that analyzes citizen reports to determine their priority level. Respond with only one of: LOW, MEDIUM, HIGH, or URGENT."
                            },
                            {
                                "role": "user",
                                "content": f"Analyze this report and determine its priority level: {report_text}"
                            }
                        ]
                    }
                )
                priority_response.raise_for_status()
                priority = priority_response.json()['choices'][0]['message']['content'].strip()

                # Then, generate summary
                summary_response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "llama2-70b",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an AI assistant that generates concise summaries of citizen reports. Keep summaries under 200 characters."
                            },
                            {
                                "role": "user",
                                "content": f"Generate a concise summary of this report: {report_text}"
                            }
                        ]
                    }
                )
                summary_response.raise_for_status()
                summary = summary_response.json()['choices'][0]['message']['content'].strip()

                # Cache the results
                cache.set(cache_key, {
                    'priority': priority,
                    'summary': summary
                }, self.CACHE_TTL)

                return priority, summary

        except httpx.HTTPError as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            return "MEDIUM", ""  # Default values if API fails
        except Exception as e:
            logger.error(f"Unexpected error in OpenRouter integration: {str(e)}")
            return "MEDIUM", ""

    async def transcribe_voice_note(self, audio_url: str, source_language: str = "ig") -> Optional[str]:
        """Transcribe voice note using OpenRouter's speech-to-text.
        
        Args:
            audio_url (str): URL of the voice note to transcribe
            source_language (str): Source language code (ig=Igbo, en=English, pcm=Nigerian Pidgin)
            
        Returns:
            Optional[str]: Transcribed text or None if transcription fails
        """
        cache_key = f"voice_transcription_{hash(audio_url)}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result

        try:
            async with httpx.AsyncClient() as client:
                # Download audio file
                audio_response = await client.get(audio_url)
                audio_response.raise_for_status()
                audio_data = audio_response.content

                # Request transcription
                transcription_response = await client.post(
                    f"{self.BASE_URL}/audio/transcriptions",
                    headers=self.headers,
                    files={
                        'file': ('audio.mp3', audio_data, 'audio/mpeg'),
                        'model': (None, 'whisper-1'),
                        'language': (None, source_language)
                    }
                )
                transcription_response.raise_for_status()
                transcription = transcription_response.json()['text']

                # Cache the result
                cache.set(cache_key, transcription, self.CACHE_TTL)

                return transcription

        except httpx.HTTPError as e:
            logger.error(f"OpenRouter transcription API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in transcription: {str(e)}")
            return None

    async def generate_summary(self, text: str) -> Optional[str]:
        """Generate a summary of the given text.
        
        Args:
            text: Text to summarize
            
        Returns:
            Generated summary or None if generation fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.BASE_URL}/chat/completions',
                    headers=self.headers,
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
            logger.error(f'Failed to generate summary: {str(e)}')
            return None
    
    async def calculate_priority(self, text: str) -> Optional[float]:
        """Calculate priority score for the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Priority score between 0 and 1, or None if calculation fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.BASE_URL}/chat/completions',
                    headers=self.headers,
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
            logger.error(f'Failed to calculate priority: {str(e)}')
            return None
    
    async def translate_text(self, text: str, source_lang: str, target_lang: str = 'en') -> str:
        """Translate text between languages.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code (default: en)
            
        Returns:
            Translated text or original text if translation fails
        """
        if not text or source_lang == target_lang:
            return text
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.BASE_URL}/chat/completions',
                    headers=self.headers,
                    json={
                        'model': 'mistral/mistral-7b',
                        'messages': [
                            {
                                'role': 'system',
                                'content': f'Translate the following text from {source_lang} to {target_lang}.'
                            },
                            {
                                'role': 'user',
                                'content': text
                            }
                        ]
                    }
                )
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            logger.error(f'Translation failed: {str(e)}')
            return text
    
    async def transcribe_audio(self, audio_url: str) -> Optional[str]:
        """Transcribe audio to text.
        
        Args:
            audio_url: URL of the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.BASE_URL}/transcribe',
                    headers=self.headers,
                    json={'audio_url': audio_url}
                )
                response.raise_for_status()
                return response.json()['text']
                
        except Exception as e:
            logger.error(f'Transcription failed: {str(e)}')
            return None 