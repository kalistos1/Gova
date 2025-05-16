"""Flutterwave payment integration client."""

import httpx
import logging
from django.conf import settings
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FlutterwaveClient:
    """Client for Flutterwave payment services."""
    
    def __init__(self):
        """Initialize the Flutterwave client."""
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY
        self.public_key = settings.FLUTTERWAVE_PUBLIC_KEY
        self.base_url = 'https://api.flutterwave.com/v3'
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    async def initialize_payment(
        self,
        amount: float,
        email: str,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        tx_ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initialize a payment transaction.
        
        Args:
            amount: Amount to charge in Naira
            email: Customer's email address
            phone: Customer's phone number (optional)
            name: Customer's full name (optional)
            tx_ref: Unique transaction reference (optional)
            
        Returns:
            Dict containing payment initialization details
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            payload = {
                'amount': amount,
                'currency': 'NGN',
                'payment_options': 'card,ussd,bank_transfer',
                'customer': {
                    'email': email,
                    'phonenumber': phone,
                    'name': name
                },
                'customizations': {
                    'title': 'AbiaHub Report Payment',
                    'description': 'Payment for report submission',
                    'logo': settings.FLUTTERWAVE_LOGO_URL
                },
                'tx_ref': tx_ref or f'abiahub_{datetime.now().timestamp()}'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.base_url}/payments',
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    'status': data.get('status', 'error'),
                    'message': data.get('message', ''),
                    'data': {
                        'link': data.get('data', {}).get('link'),
                        'tx_ref': data.get('data', {}).get('tx_ref'),
                        'amount': amount,
                        'currency': 'NGN'
                    }
                }
                
        except Exception as e:
            logger.error(f'Payment initialization failed: {str(e)}')
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }
    
    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Verify a payment transaction.
        
        Args:
            transaction_id: Flutterwave transaction ID
            
        Returns:
            Dict containing verification result
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/transactions/{transaction_id}/verify',
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    'status': data.get('data', {}).get('status', 'failed'),
                    'amount': data.get('data', {}).get('amount'),
                    'currency': data.get('data', {}).get('currency'),
                    'customer': {
                        'email': data.get('data', {}).get('customer', {}).get('email'),
                        'phone': data.get('data', {}).get('customer', {}).get('phone_number'),
                        'name': data.get('data', {}).get('customer', {}).get('name')
                    },
                    'transaction_id': transaction_id,
                    'tx_ref': data.get('data', {}).get('tx_ref'),
                    'payment_type': data.get('data', {}).get('payment_type')
                }
                
        except Exception as e:
            logger.error(f'Payment verification failed: {str(e)}')
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Initiate a refund for a transaction.
        
        Args:
            transaction_id: Flutterwave transaction ID
            amount: Amount to refund (optional, defaults to full amount)
            
        Returns:
            Dict containing refund result
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            payload = {'amount': amount} if amount else {}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.base_url}/transactions/{transaction_id}/refund',
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    'status': data.get('status', 'error'),
                    'message': data.get('message', ''),
                    'data': {
                        'refund_id': data.get('data', {}).get('id'),
                        'amount': data.get('data', {}).get('amount'),
                        'currency': data.get('data', {}).get('currency'),
                        'transaction_id': transaction_id
                    }
                }
                
        except Exception as e:
            logger.error(f'Refund initiation failed: {str(e)}')
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            } 