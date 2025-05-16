"""URL patterns for the proposals API.

This module defines the URL patterns for the proposals API endpoints:
- GET/POST /api/proposals/: List and create proposals
- GET /api/proposals/{id}/: Retrieve specific proposal
- POST /api/proposals/{id}/votes/: Add vote to proposal

The API follows RESTful conventions and uses UUIDs for proposal identification.
All endpoints return JSON responses in camelCase format.

Example:
    GET /api/proposals/?status=active&category=infrastructure
    POST /api/proposals/ (authenticated)
    GET /api/proposals/123e4567-e89b-12d3-a456-426614174000/
    POST /api/proposals/123e4567-e89b-12d3-a456-426614174000/votes/ (authenticated)
"""

from django.urls import path
from . import views

app_name = 'proposals'

urlpatterns = [
    # List and create proposals
    path(
        '',
        views.proposal_list,
        name='proposal-list',
        kwargs={'http_method_names': ['get']}
    ),
    path(
        '',
        views.proposal_create,
        name='proposal-create',
        kwargs={'http_method_names': ['post']}
    ),
    
    # Retrieve specific proposal
    path(
        '<uuid:pk>/',
        views.proposal_detail,
        name='proposal-detail',
        kwargs={'http_method_names': ['get']}
    ),
    
    # Add vote to proposal
    path(
        '<uuid:pk>/votes/',
        views.proposal_vote,
        name='proposal-vote',
        kwargs={'http_method_names': ['post']}
    ),
]
