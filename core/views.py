from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from reports.models import Report
from proposals.models import Proposal
from services.models import ServiceRequest
# from grants.models import Grant
from .models import Reward


def index(request):
    """
    View for the index page.
    """
    return render(request, 'pages/index.html')



@login_required
def citizen_dashboard(request):
    """
    View for the citizen dashboard showing reports, proposals, services, and rewards.
    """
    # Get user's reports
    reports_count = Report.objects.filter(user=request.user).count()
    pending_reports_count = Report.objects.filter(
        user=request.user,
        status='pending'
    ).count()
    
    # Get user's proposals
    proposals_count = Proposal.objects.filter(user=request.user).count()
    votes_received = Proposal.objects.filter(user=request.user).aggregate(
        total_votes=Count('votes')
    )['total_votes'] or 0
    
    # Get user's service requests
    services_count = ServiceRequest.objects.filter(user=request.user).count()
    active_services = ServiceRequest.objects.filter(
        user=request.user,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Get user's rewards
    rewards_count = Reward.objects.filter(user=request.user).count()
    airtime_rewards = Reward.objects.filter(
        user=request.user,
        type='airtime'
    ).count()
    
    # Get upcoming deadlines
    today = timezone.now()
    deadlines = []
    
    # Service deadlines
    service_deadlines = ServiceRequest.objects.filter(
        user=request.user,
        due_date__gt=today,
        status__in=['pending', 'in_progress']
    ).order_by('due_date')[:5]
    
    for service in service_deadlines:
        days_left = (service.due_date - today).days
        total_days = (service.due_date - service.created_at).days
        progress = ((total_days - days_left) / total_days) * 100 if total_days > 0 else 0
        
        deadlines.append({
            'title': f'Service: {service.service_type}',
            'start_date': service.created_at,
            'due_date': service.due_date,
            'days_left': days_left,
            'progress': progress,
            'action_url': service.get_absolute_url()
        })
    
    # Grant deadlines
    grant_deadlines = Grant.objects.filter(
        applications__user=request.user,
        deadline__gt=today
    ).order_by('deadline')[:5]
    
    for grant in grant_deadlines:
        days_left = (grant.deadline - today).days
        total_days = (grant.deadline - grant.start_date).days
        progress = ((total_days - days_left) / total_days) * 100 if total_days > 0 else 0
        
        deadlines.append({
            'title': f'Grant: {grant.title}',
            'start_date': grant.start_date,
            'due_date': grant.deadline,
            'days_left': days_left,
            'progress': progress,
            'action_url': grant.get_absolute_url()
        })
    
    # Sort deadlines by days left
    deadlines.sort(key=lambda x: x['days_left'])
    
    context = {
        'reports_count': reports_count,
        'pending_reports_count': pending_reports_count,
        'proposals_count': proposals_count,
        'votes_received': votes_received,
        'services_count': services_count,
        'active_services': active_services,
        'rewards_count': rewards_count,
        'airtime_rewards': airtime_rewards,
        'deadlines': deadlines[:5]  # Show only top 5 deadlines
    }
    
    return render(request, 'dashboards/citizen.html', context)

@login_required
def user_reports_list(request):
    """
    View for the HTMX-powered reports list in the citizen dashboard.
    """
    reports = Report.objects.filter(user=request.user).order_by('-created_at')
    
    # Add pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(reports, 10)  # Show 10 reports per page
    
    try:
        reports = paginator.page(page)
    except PageNotAnInteger:
        reports = paginator.page(1)
    except EmptyPage:
        reports = paginator.page(paginator.num_pages)
    
    return render(request, 'partials/report_list.html', {'reports': reports})

@login_required
def user_deadlines_list(request):
    """
    View for the HTMX-powered deadlines list in the citizen dashboard.
    """
    today = timezone.now()
    deadlines = []
    
    # Service deadlines
    service_deadlines = ServiceRequest.objects.filter(
        user=request.user,
        due_date__gt=today,
        status__in=['pending', 'in_progress']
    ).order_by('due_date')
    
    for service in service_deadlines:
        days_left = (service.due_date - today).days
        total_days = (service.due_date - service.created_at).days
        progress = ((total_days - days_left) / total_days) * 100 if total_days > 0 else 0
        
        deadlines.append({
            'title': f'Service: {service.service_type}',
            'start_date': service.created_at,
            'due_date': service.due_date,
            'days_left': days_left,
            'progress': progress,
            'action_url': service.get_absolute_url()
        })
    
    # Grant deadlines
    grant_deadlines = Grant.objects.filter(
        applications__user=request.user,
        deadline__gt=today
    ).order_by('deadline')
    
    for grant in grant_deadlines:
        days_left = (grant.deadline - today).days
        total_days = (grant.deadline - grant.start_date).days
        progress = ((total_days - days_left) / total_days) * 100 if total_days > 0 else 0
        
        deadlines.append({
            'title': f'Grant: {grant.title}',
            'start_date': grant.start_date,
            'due_date': grant.deadline,
            'days_left': days_left,
            'progress': progress,
            'action_url': grant.get_absolute_url()
        })
    
    # Sort deadlines by days left
    deadlines.sort(key=lambda x: x['days_left'])
    
    # Add pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(deadlines, 5)  # Show 5 deadlines per page
    
    try:
        deadlines = paginator.page(page)
    except PageNotAnInteger:
        deadlines = paginator.page(1)
    except EmptyPage:
        deadlines = paginator.page(paginator.num_pages)
    
    return render(request, 'partials/deadlines_list.html', {'deadlines': deadlines})
