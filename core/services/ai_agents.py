"""AI agents for voice transcription and issue prioritization."""

import logging
import json
from typing import List, Dict, Any, Optional
import aiohttp
from django.conf import settings
from django.core.cache import cache
from .base import BaseService

logger = logging.getLogger(__name__)

class AIService(BaseService):
    """Handles AI-powered features using OpenRouter API."""
    
    def __init__(self):
        super().__init__()
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self.llama_model = settings.LLAMA_MODEL_ID
        self.speech_model = settings.SPEECH_TO_TEXT_MODEL
        
    async def transcribe_voice(
        self,
        audio_file: bytes,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Transcribe voice message to text.
        
        Args:
            audio_file: Audio file bytes
            language: Language code (en/ig/pcm for English/Igbo/Pidgin)
            
        Returns:
            Dict containing transcribed text and metadata
        """
        try:
            # Check cache first
            cache_key = f"voice_transcript_{hash(audio_file)}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "audio/wav"  # Adjust based on input format
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/speech/transcribe",
                    headers=headers,
                    data=audio_file,
                    params={"language": language}
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    # Cache result for 1 hour
                    cache.set(cache_key, result, 3600)
                    
                    return {
                        'status': 'success',
                        'text': result['text'],
                        'language': result['detected_language'],
                        'confidence': result['confidence']
                    }
                    
        except Exception as e:
            logger.error(f"Voice transcription failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    async def prioritize_issues(
        self,
        reports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize issues using LLaMA model.
        
        Args:
            reports: List of report dictionaries
            
        Returns:
            List of reports with priority scores and reasoning
        """
        try:
            # Check cache first
            cache_key = f"issue_priority_{hash(json.dumps(reports))}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare prompt for batch processing
            prompt = self._prepare_priority_prompt(reports)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.llama_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are an AI assistant that helps prioritize "
                                    "civic issues based on urgency and impact."
                                )
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    # Parse AI response
                    priorities = self._parse_priority_response(
                        result['choices'][0]['message']['content']
                    )
                    
                    # Combine original reports with priorities
                    prioritized_reports = []
                    for report, priority in zip(reports, priorities):
                        report.update(priority)
                        prioritized_reports.append(report)
                    
                    # Cache result for 30 minutes
                    cache.set(cache_key, prioritized_reports, 1800)
                    
                    return prioritized_reports
                    
        except Exception as e:
            logger.error(f"Issue prioritization failed: {str(e)}")
            return reports  # Return original reports without priorities
            
    def _prepare_priority_prompt(
        self,
        reports: List[Dict[str, Any]]
    ) -> str:
        """Prepare prompt for issue prioritization.
        
        Args:
            reports: List of report dictionaries
            
        Returns:
            Formatted prompt string
        """
        prompt = (
            "Please analyze the following civic issues and assign priority scores "
            "(0-1) based on urgency and potential impact. For each issue, provide "
            "a brief reasoning.\n\n"
        )
        
        for i, report in enumerate(reports, 1):
            prompt += (
                f"Issue {i}:\n"
                f"Title: {report['title']}\n"
                f"Description: {report['description']}\n"
                f"Location: {report['location']}\n"
                f"Category: {report['category']}\n\n"
            )
            
        return prompt
        
    def _parse_priority_response(
        self,
        response: str
    ) -> List[Dict[str, Any]]:
        """Parse AI response into structured priority data.
        
        Args:
            response: AI model response string
            
        Returns:
            List of priority dictionaries
        """
        try:
            # Implement parsing logic based on response format
            # This is a simplified example
            priorities = []
            
            # Split response by issues
            issues = response.split("Issue")[1:]  # Skip first empty part
            
            for issue in issues:
                # Extract priority score and reasoning
                # This parsing logic should match your AI model's output format
                if "Priority Score:" in issue and "Reasoning:" in issue:
                    score_text = issue.split("Priority Score:")[1].split("Reasoning:")[0]
                    reasoning = issue.split("Reasoning:")[1].split("\n")[0]
                    
                    try:
                        score = float(score_text.strip())
                        priorities.append({
                            'priority_score': score,
                            'urgency_level': self._score_to_level(score),
                            'reasoning': reasoning.strip()
                        })
                    except ValueError:
                        logger.error(f"Failed to parse priority score: {score_text}")
                        priorities.append({
                            'priority_score': 0.5,
                            'urgency_level': 'medium',
                            'reasoning': 'Score parsing failed'
                        })
                        
            return priorities
            
        except Exception as e:
            logger.error(f"Priority response parsing failed: {str(e)}")
            return [
                {
                    'priority_score': 0.5,
                    'urgency_level': 'medium',
                    'reasoning': 'Parsing failed'
                }
            ] * len(response.split("Issue")) # Return default priorities
            
    def _score_to_level(self, score: float) -> str:
        """Convert priority score to urgency level.
        
        Args:
            score: Priority score (0-1)
            
        Returns:
            Urgency level string
        """
        if score >= 0.8:
            return 'critical'
        elif score >= 0.6:
            return 'high'
        elif score >= 0.4:
            return 'medium'
        elif score >= 0.2:
            return 'low'
        else:
            return 'minimal' 