from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from .models import Proposal, Vote, Reward
from .serializers import ProposalSerializer, ProposalCreateSerializer, VoteSerializer
from core.models import AuditLog

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for proposal listings."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

def create_reward(
    user,
    proposal,
    action_type: str,
    retry_attempts: int = 3
) -> Optional[Reward]:
    """Create a reward for proposal creation or voting.
    
    Args:
        user: The user to reward.
        proposal: The proposal being acted upon.
        action_type: Either 'proposal_created' or 'vote_added'.
        retry_attempts: Number of times to retry on failure.
        
    Returns:
        Optional[Reward]: Created reward or None if creation fails.
        
    Raises:
        ValidationError: If input data is invalid.
    """
    try:
        # Validate input
        if not user:
            raise ValidationError(_('User is required'))
        if not proposal:
            raise ValidationError(_('Proposal is required'))
        if action_type not in ['proposal_created', 'vote_added']:
            raise ValidationError(_('Invalid action type'))
            
        # Get reward amount from settings
        try:
            reward_amount = (
                Decimal(settings.PROPOSAL_REWARD_AMOUNT)
                if action_type == 'proposal_created'
                else Decimal(settings.VOTE_REWARD_AMOUNT)
            )
        except (AttributeError, ValueError) as e:
            logger.error(
                'Invalid reward amount in settings',
                extra={
                    'error': str(e),
                    'action_type': action_type
                }
            )
            raise ValidationError(_('Invalid reward amount configuration'))
            
        # Check for duplicate rewards
        existing_reward = Reward.objects.filter(
            user=user,
            proposal=proposal,
            action_type=action_type
        ).first()
        if existing_reward:
            logger.warning(
                'Duplicate reward prevented',
                extra={
                    'user_id': user.id,
                    'proposal_id': proposal.id,
                    'action_type': action_type
                }
            )
            return existing_reward
            
        # Create reward with retry
        for attempt in range(retry_attempts):
            try:
                reward = Reward.objects.create(
                    user=user,
                    proposal=proposal,
                    amount=reward_amount,
                    action_type=action_type
                )
                
                # Log success
                logger.info(
                    'Reward created successfully',
                    extra={
                        'reward_id': reward.id,
                        'user_id': user.id,
                        'proposal_id': proposal.id,
                        'action_type': action_type,
                        'amount': str(reward_amount)
                    }
                )
                
                return reward
                
            except Exception as e:
                logger.warning(
                    'Reward creation failed',
                    extra={
                        'error': str(e),
                        'attempt': attempt + 1,
                        'user_id': user.id,
                        'proposal_id': proposal.id,
                        'action_type': action_type
                    }
                )
                if attempt == retry_attempts - 1:
                    raise
                    
        return None
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(
            'Failed to create reward',
            extra={
                'error': str(e),
                'user_id': user.id if user else None,
                'proposal_id': proposal.id if proposal else None,
                'action_type': action_type
            },
            exc_info=True
        )
        return None

@api_view(['GET'])
@permission_classes([AllowAny])
def proposal_list(request):
    """List all proposals with filtering and pagination.
    
    Args:
        request: HTTP request object containing query parameters.
            - status: Filter by proposal status
            - category: Filter by proposal category
            - location: Filter by location ID
            
    Returns:
        Paginated list of proposals in camelCase format.
    """
    try:
        queryset = Proposal.objects.select_related(
            'location', 'landmark'
        ).prefetch_related('votes').annotate(
            vote_count=Count('votes')
        )
        
        # Apply filters
        status = request.query_params.get('status')
        category = request.query_params.get('category')
        location = request.query_params.get('location')
        
        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        if location:
            queryset = queryset.filter(location_id=location)
            
        # Apply pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        serializer = ProposalSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
        
    except Exception as e:
        logger.error(
            'Error listing proposals',
            extra={
                'error': str(e),
                'filters': {
                    'status': status,
                    'category': category,
                    'location': location
                }
            },
            exc_info=True
        )
        return Response(
            {'error': _('Failed to retrieve proposals')},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proposal_create(request):
    """Create a new proposal and trigger reward creation.
    
    Args:
        request: HTTP request object containing proposal data.
            
    Returns:
        Created proposal data in camelCase format.
        
    Raises:
        400: If required fields are missing or invalid.
        500: If proposal or reward creation fails.
    """
    try:
        serializer = ProposalCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        # Create proposal
        proposal = serializer.save(created_by=request.user)
        
        # Create reward
        reward = create_reward(request.user, proposal, 'proposal_created')
        if not reward:
            logger.error(
                'Failed to create reward for proposal',
                extra={
                    'user_id': request.user.id,
                    'proposal_id': proposal.id
                }
            )
        
        # Log action
        AuditLog.objects.create(
            action='Proposal Created',
            user=request.user,
            details={
                'proposal_id': str(proposal.id),
                'title': proposal.title,
                'category': proposal.category,
                'reward_created': bool(reward)
            }
        )
        
        return Response(
            ProposalSerializer(proposal).data,
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(
            'Error creating proposal',
            extra={
                'error': str(e),
                'user_id': request.user.id,
                'data': request.data
            },
            exc_info=True
        )
        return Response(
            {'error': _('Failed to create proposal')},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def proposal_detail(request, pk):
    """Retrieve a specific proposal by ID.
    
    Args:
        request: HTTP request object.
        pk: UUID of the proposal to retrieve.
            
    Returns:
        Proposal data in camelCase format.
        
    Raises:
        404: If proposal not found.
        500: If retrieval fails.
    """
    try:
        proposal = get_object_or_404(
            Proposal.objects.select_related(
                'location', 'landmark'
            ).prefetch_related('votes').annotate(
                vote_count=Count('votes')
            ),
            pk=pk
        )
        serializer = ProposalSerializer(proposal)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(
            'Error retrieving proposal',
            extra={
                'error': str(e),
                'proposal_id': pk
            },
            exc_info=True
        )
        return Response(
            {'error': _('Failed to retrieve proposal')},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proposal_vote(request, pk):
    """Add a vote to a proposal and trigger reward creation.
    
    Args:
        request: HTTP request object.
        pk: UUID of the proposal to vote on.
            
    Returns:
        Created vote data in camelCase format.
        
    Raises:
        404: If proposal not found.
        400: If user has already voted.
        403: If proposal is not in votable status.
        500: If vote or reward creation fails.
    """
    try:
        proposal = get_object_or_404(
            Proposal.objects.select_related(
                'location', 'landmark'
            ),
            pk=pk
        )
        
        # Check if proposal is votable
        if proposal.status not in ['draft', 'active']:
            return Response(
                {'error': _('This proposal is not currently accepting votes')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has already voted
        if Vote.objects.filter(proposal=proposal, user=request.user).exists():
            return Response(
                {'error': _('You have already voted on this proposal')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create vote
        vote_data = {'proposal': proposal.id, 'user': request.user.id}
        serializer = VoteSerializer(data=vote_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        vote = serializer.save()
        
        # Create reward
        reward = create_reward(request.user, proposal, 'vote_added')
        if not reward:
            logger.error(
                'Failed to create reward for vote',
                extra={
                    'user_id': request.user.id,
                    'proposal_id': proposal.id,
                    'vote_id': vote.id
                }
            )
        
        # Log action
        AuditLog.objects.create(
            action='Vote Added',
            user=request.user,
            details={
                'proposal_id': str(proposal.id),
                'vote_id': str(vote.id),
                'reward_created': bool(reward)
            }
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(
            'Error adding vote',
            extra={
                'error': str(e),
                'user_id': request.user.id,
                'proposal_id': pk
            },
            exc_info=True
        )
        return Response(
            {'error': _('Failed to add vote')},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Web template views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q, Count

def proposals_list_view(request):
    """View to display list of proposals with filtering and pagination."""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    proposals = Proposal.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter:
        proposals = proposals.filter(status=status_filter)
    
    if category_filter:
        proposals = proposals.filter(category_id=category_filter)
    
    if search_query:
        proposals = proposals.filter(
            Q(title__icontains=search_query) | 
            Q(summary__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Annotate with vote count
    proposals = proposals.annotate(votes_count=Count('votes'))
    
    # Pagination
    paginator = Paginator(proposals, 10)  # 10 proposals per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = Category.objects.all()
    
    context = {
        'proposals': page_obj,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'search_query': search_query,
    }
    
    # If this is an HTMX request, render only the proposals list
    if request.headers.get('HX-Request'):
        return render(request, 'proposals/_proposals_list.html', context)
    
    return render(request, 'proposals/list.html', context)

def proposals_search_view(request):
    """View to handle HTMX search requests for proposals."""
    search_query = request.GET.get('q', '')
    
    proposals = Proposal.objects.filter(
        Q(title__icontains=search_query) | 
        Q(summary__icontains=search_query) |
        Q(description__icontains=search_query)
    ).order_by('-created_at').annotate(votes_count=Count('votes'))
    
    # Pagination
    paginator = Paginator(proposals, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'proposals': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'proposals/_proposals_list.html', context)

def proposal_detail_view(request, proposal_id):
    """View to display a single proposal with comments and related actions."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    # Get related proposals (same category, excluding current)
    related_proposals = Proposal.objects.filter(
        category=proposal.category
    ).exclude(id=proposal_id).order_by('-created_at')[:5]
    
    # Check if user has voted for this proposal
    user_has_voted = False
    if request.user.is_authenticated:
        user_has_voted = proposal.votes.filter(user=request.user).exists()
    
    # Check if a new comment was just added (for highlighting)
    new_comment = request.GET.get('new_comment', False)
    
    context = {
        'proposal': proposal,
        'related_proposals': related_proposals,
        'user_has_voted': user_has_voted,
        'new_comment': new_comment,
    }
    
    return render(request, 'proposals/detail.html', context)

@login_required
def proposal_create_view(request):
    """View to handle proposal creation."""
    if request.method == 'POST':
        form = ProposalForm(request.POST)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.author = request.user
            proposal.status = 'draft'
            proposal.save()
            
            messages.success(request, 'Proposal created successfully!')
            return redirect('proposals:detail', proposal_id=proposal.id)
    else:
        form = ProposalForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'proposals/form.html', context)

@login_required
def proposal_edit_view(request, proposal_id):
    """View to handle proposal editing."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    # Check if user is authorized to edit
    if proposal.author != request.user and not request.user.is_staff:
        messages.error(request, 'You are not authorized to edit this proposal.')
        return redirect('proposals:detail', proposal_id=proposal.id)
    
    # Check if proposal is in draft status (unless admin)
    if proposal.status != 'draft' and not request.user.is_staff:
        messages.error(request, 'Only draft proposals can be edited.')
        return redirect('proposals:detail', proposal_id=proposal.id)
    
    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proposal updated successfully!')
            return redirect('proposals:detail', proposal_id=proposal.id)
    else:
        form = ProposalForm(instance=proposal)
    
    context = {
        'form': form,
        'proposal': proposal,
        'is_create': False,
    }
    
    return render(request, 'proposals/form.html', context)

@login_required
def proposal_delete_view(request, proposal_id):
    """View to handle proposal deletion."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    # Check if user is authorized to delete
    if proposal.author != request.user and not request.user.is_staff:
        messages.error(request, 'You are not authorized to delete this proposal.')
        return redirect('proposals:detail', proposal_id=proposal.id)
    
    if request.method == 'POST':
        proposal.delete()
        messages.success(request, 'Proposal deleted successfully!')
        return redirect('proposals:list')
    
    context = {
        'proposal': proposal,
    }
    
    return render(request, 'proposals/delete_confirm.html', context)

@login_required
def proposal_add_comment_view(request, proposal_id):
    """HTMX view to add a comment to a proposal."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if content:
            comment = Comment.objects.create(
                content=content,
                author=request.user,
                proposal=proposal
            )
            
            context = {
                'comment': comment,
                'new_comment': True,
            }
            
            return render(request, 'proposals/_comment.html', context)
    
    # Return an empty response if something went wrong
    return HttpResponse(status=400)

@login_required
def proposal_vote_view(request, proposal_id):
    """HTMX view to handle voting on a proposal."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    # Check if user has already voted
    if not proposal.votes.filter(user=request.user).exists():
        Vote.objects.create(
            user=request.user,
            proposal=proposal
        )
    
    # Get updated vote count
    votes_count = proposal.votes.count()
    
    context = {
        'proposal': proposal,
        'votes_count': votes_count,
        'user_has_voted': True,
    }
    
    return render(request, 'proposals/_vote_section.html', context)

@login_required
def proposal_update_status_view(request, proposal_id):
    """HTMX view to update proposal status."""
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    # Check permissions
    is_author = request.user == proposal.author
    is_staff = request.user.is_staff
    
    if not (is_author or is_staff):
        return HttpResponse(status=403)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        # Validate the status
        valid_statuses = [choice[0] for choice in Proposal.STATUS_CHOICES]
        
        if new_status in valid_statuses:
            # Authors can only submit their own draft proposals
            if is_author and not is_staff:
                if proposal.status == 'draft' and new_status == 'submitted':
                    proposal.status = new_status
                    proposal.save()
                    messages.success(request, 'Proposal submitted successfully!')
                else:
                    return HttpResponse(status=403)
            # Staff can change to any status
            elif is_staff:
                proposal.status = new_status
                proposal.save()
                messages.success(request, f'Proposal status updated to {proposal.get_status_display()}')
        
        return redirect('proposals:detail', proposal_id=proposal.id)
    
    return HttpResponse(status=400)

@login_required
def proposal_upload_attachment_view(request):
    """HTMX view to handle file uploads for proposal attachments."""
    if request.method == 'POST' and request.FILES.get('file'):
        file_obj = request.FILES['file']
        proposal_id = request.POST.get('proposal_id')
        
        if not proposal_id:
            return HttpResponse(status=400)
        
        try:
            proposal = Proposal.objects.get(id=proposal_id)
            
            # Check if user is authorized to upload
            if proposal.author != request.user and not request.user.is_staff:
                return HttpResponse(status=403)
            
            # Create the attachment
            attachment = Attachment.objects.create(
                file=file_obj,
                proposal=proposal,
                uploaded_by=request.user
            )
            
            context = {
                'attachment': attachment,
            }
            
            return render(request, 'proposals/_attachment.html', context)
            
        except Proposal.DoesNotExist:
            return HttpResponse(status=404)
    
    return HttpResponse(status=400)
