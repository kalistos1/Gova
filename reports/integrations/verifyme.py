"""VerifyMe integration for NIN verification."""

import httpx
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class VerifyMeClient:
    """Client for VerifyMe NIN verification service."""

    BASE_URL = "https://vapi.verifyme.ng/v1"

    def __init__(self):
        """Initialize the VerifyMe client."""
        self.api_key = settings.VERIFYME_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def verify_nin(self, nin: str, phone_number: str) -> Optional[Dict]:
        """Verify a user's NIN and phone number.
        
        Args:
            nin (str): National Identity Number
            phone_number (str): User's phone number
            
        Returns:
            Optional[Dict]: Verification result or None if verification fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/nin/verify",
                    headers=self.headers,
                    json={
                        "nin": nin,
                        "phoneNumber": phone_number
                    }
                )
                response.raise_for_status()
                result = response.json()

                # Log successful verification
                logger.info(f"Successfully verified NIN for phone number: {phone_number}")

                return {
                    'verified': True,
                    'first_name': result.get('data', {}).get('firstName'),
                    'last_name': result.get('data', {}).get('lastName'),
                    'phone_number': result.get('data', {}).get('phoneNumber'),
                    'state_of_origin': result.get('data', {}).get('stateOfOrigin'),
                    'lga_of_origin': result.get('data', {}).get('lgaOfOrigin')
                }

        except httpx.HTTPError as e:
            logger.error(f"VerifyMe API error: {str(e)}")
            if e.response and e.response.status_code == 404:
                return {
                    'verified': False,
                    'error': 'NIN not found'
                }
            return {
                'verified': False,
                'error': 'Verification service unavailable'
            }
        except Exception as e:
            logger.error(f"Unexpected error in NIN verification: {str(e)}")
            return {
                'verified': False,
                'error': 'Internal server error'
            }

    async def verify_bvn(self, bvn: str) -> Optional[Dict]:
        """Verify a user's Bank Verification Number (BVN).
        
        Args:
            bvn (str): Bank Verification Number
            
        Returns:
            Optional[Dict]: Verification result or None if verification fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/bvn/verify",
                    headers=self.headers,
                    json={"bvn": bvn}
                )
                response.raise_for_status()
                result = response.json()

                # Log successful verification
                logger.info(f"Successfully verified BVN")

                return {
                    'verified': True,
                    'first_name': result.get('data', {}).get('firstName'),
                    'last_name': result.get('data', {}).get('lastName'),
                    'phone_number': result.get('data', {}).get('phoneNumber'),
                    'date_of_birth': result.get('data', {}).get('dateOfBirth')
                }

        except httpx.HTTPError as e:
            logger.error(f"VerifyMe BVN API error: {str(e)}")
            return {
                'verified': False,
                'error': 'BVN verification failed'
            }
        except Exception as e:
            logger.error(f"Unexpected error in BVN verification: {str(e)}")
            return {
                'verified': False,
                'error': 'Internal server error'
            } 