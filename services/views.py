"""Service views for handling service requests and payments."""

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests
import logging
from typing import Dict, Any, Optional
import uuid

from .models import Service, ServiceRequest
from .serializers import (
    ServiceSerializer, ServiceRequestSerializer,
    ServiceRequestCreateSerializer, ServiceRequestUpdateSerializer
)
from .permissions import IsStateOfficial
from core.models import AuditLog

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for service listings."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

def initiate_flutterwave_payment(data: Dict[str, Any], user) -> Dict[str, Any]:
    """Initialize payment with Flutterwave.
    
    Args:
        data: Validated service request data
        user: User making the request
        
    Returns:
        dict: Payment initialization response
        
    Raises:
        requests.RequestException: If payment service is unavailable
    """
    service = data['service']
    amount = data['amount']
    
    # Generate unique transaction reference
    tx_ref = f"SRV-{uuid.uuid4().hex[:8]}"
    
    # Prepare payment data
    payment_data = {
        'tx_ref': tx_ref,
        'amount': str(amount),
        'currency': 'NGN',
        'redirect_url': f"{settings.FRONTEND_URL}/service-requests/verify",
        'payment_options': 'card,ussd,bank_transfer',
        'customer': {
            'email': user.email,
            'phonenumber': user.phone_number,
            'name': user.get_full_name() or user.username
        },
        'customizations': {
            'title': f"Payment for {service.name}",
            'description': f"Service request payment for {service.name}",
            'logo': settings.FLUTTERWAVE_LOGO_URL
        },
        'meta': {
            'service_id': str(service.id),
            'user_id': str(user.id)
        }
    }
    
    # Make API request to Flutterwave
    headers = {
        'Authorization': f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        'Content-Type': 'application/json'
    }
    
    response = requests.post(
        'https://api.flutterwave.com/v3/payments',
        json=payment_data,
        headers=headers
    )
    response.raise_for_status()
    
    return response.json()

@api_view(['GET'])
@permission_classes([AllowAny])
def service_list(request):
    """List all services with filtering and pagination.
    
    Args:
        request: HTTP request object containing query parameters.
            - category: Filter by service category
            
    Returns:
        Paginated list of services in camelCase format.
    """
    queryset = Service.objects.filter(is_active=True)
    
    # Apply filters
    category = request.query_params.get('category')
    if category:
        queryset = queryset.filter(category=category)
        
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = ServiceSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def service_detail(request, pk):
    """Retrieve a specific service by ID.
    
    Args:
        request: HTTP request object.
        pk: UUID of the service to retrieve.
            
    Returns:
        Service data in camelCase format.
        
    Raises:
        404: If service not found.
    """
    service = get_object_or_404(Service.objects.filter(is_active=True), pk=pk)
    serializer = ServiceSerializer(service)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def service_request_create(request):
    """Create a new service request and initiate payment.
    
    Args:
        request: HTTP request object containing service request data.
            
    Returns:
        Created service request data in camelCase format with payment details.
        
    Raises:
        400: If required fields are missing or invalid.
        503: If payment service is unavailable.
    """
    serializer = ServiceRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        # Initiate payment
        payment_data = initiate_flutterwave_payment(
            serializer.validated_data,
            request.user
        )
        
        # Create service request
        service_request = serializer.save(
            user=request.user,
            payment_reference=payment_data['data']['tx_ref'],
            payment_link=payment_data['data']['link']
        )
        
        # Log action
        AuditLog.objects.create(
            action='Service Requested',
            user=request.user,
            details=f'Service request {service_request.id} created for {service_request.service.name}'
        )
        
        return Response(
            ServiceRequestSerializer(service_request).data,
            status=status.HTTP_201_CREATED
        )
    except requests.RequestException as e:
        logger.error(f"Payment service error: {str(e)}")
        return Response(
            {'error': 'Payment service is currently unavailable'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_request_list(request):
    """List all service requests for the authenticated user.
    
    Args:
        request: HTTP request object.
            
    Returns:
        Paginated list of service requests in camelCase format.
    """
    queryset = ServiceRequest.objects.select_related(
        'service', 'location', 'landmark'
    ).filter(user=request.user)
    
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = ServiceRequestSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsStateOfficial])
def service_request_update(request, pk):
    """Update service request status and payment status (state officials only).
    
    Args:
        request: HTTP request object containing update data.
        pk: UUID of the service request to update.
            
    Returns:
        Updated service request data in camelCase format.
        
    Raises:
        404: If service request not found.
        403: If user lacks permission.
        400: If update data is invalid.
    """
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related(
            'service', 'location', 'landmark'
        ),
        pk=pk
    )
    
    # Only allow updating status and payment_status
    allowed_fields = {'status', 'payment_status', 'notes'}
    if not all(field in allowed_fields for field in request.data.keys()):
        return Response(
            {'error': 'Only status, payment_status, and notes fields can be updated'},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    serializer = ServiceRequestUpdateSerializer(
        service_request,
        data=request.data,
        partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    service_request = serializer.save()
    
    # Log action
    AuditLog.objects.create(
        action='Service Request Updated',
        user=request.user,
        details=f'Service request {service_request.id} updated: {request.data}'
    )
    
    return Response(ServiceRequestSerializer(service_request).data)

# Web template views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.utils import timezone

def services_list_view(request):
    """View to display list of services with filtering and pagination."""
    # Get filter parameters
    category_filter = request.GET.get('category', '')
    location_filter = request.GET.get('location', '')
    sort_by = request.GET.get('sort_by', 'newest')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    services = Service.objects.all()
    
    # Apply filters
    if category_filter:
        services = services.filter(category_id=category_filter)
    
    if location_filter:
        services = services.filter(location_id=location_filter)
    
    if search_query:
        services = services.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'newest':
        services = services.order_by('-created_at')
    elif sort_by == 'rating':
        services = services.annotate(avg_rating=Avg('ratings__value')).order_by('-avg_rating', '-created_at')
    elif sort_by == 'popular':
        services = services.annotate(bookings_count=Count('bookings')).order_by('-bookings_count', '-created_at')
    elif sort_by == 'price_low':
        services = services.order_by('price', '-created_at')
    elif sort_by == 'price_high':
        services = services.order_by('-price', '-created_at')
    else:
        services = services.order_by('-created_at')
    
    # Annotate with average rating and ratings count
    services = services.annotate(
        average_rating=Avg('ratings__value'),
        ratings_count=Count('ratings')
    )
    
    # Pagination
    paginator = Paginator(services, 12)  # 12 services per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories and locations for filter
    categories = Category.objects.all()
    locations = Location.objects.all()
    
    context = {
        'services': page_obj,
        'categories': categories,
        'locations': locations,
        'category_filter': category_filter,
        'location_filter': location_filter,
        'sort_by': sort_by,
        'search_query': search_query,
    }
    
    # If this is an HTMX request, render only the services list
    if request.headers.get('HX-Request'):
        return render(request, 'services/_services_list.html', context)
    
    return render(request, 'services/list.html', context)

def services_search_view(request):
    """View to handle HTMX search requests for services."""
    search_query = request.GET.get('q', '')
    
    services = Service.objects.filter(
        Q(title__icontains=search_query) | 
        Q(description__icontains=search_query)
    ).order_by('-created_at').annotate(
        average_rating=Avg('ratings__value'),
        ratings_count=Count('ratings')
    )
    
    # Pagination
    paginator = Paginator(services, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'services': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'services/_services_list.html', context)

def service_detail_view(request, service_id):
    """View to display a single service with ratings and booking options."""
    service = get_object_or_404(
        Service.objects.annotate(
            average_rating=Avg('ratings__value'),
            ratings_count=Count('ratings')
        ),
        id=service_id
    )
    
    # Get related services (same category, excluding current)
    related_services = Service.objects.filter(
        category=service.category
    ).exclude(id=service_id).annotate(
        average_rating=Avg('ratings__value'),
        ratings_count=Count('ratings')
    ).order_by('-average_rating')[:3]
    
    # Check if user has already rated this service
    user_has_rated = False
    if request.user.is_authenticated:
        user_has_rated = service.ratings.filter(user=request.user).exists()
    
    context = {
        'service': service,
        'related_services': related_services,
        'user_has_rated': user_has_rated,
        'now': timezone.now(),
    }
    
    return render(request, 'services/detail.html', context)

@login_required
def service_create_view(request):
    """View to handle service creation."""
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            service.save()
            
            # Handle multiple images if provided
            if request.FILES.getlist('additional_images'):
                for image in request.FILES.getlist('additional_images'):
                    ServiceImage.objects.create(service=service, image=image)
            
            messages.success(request, 'Service created successfully!')
            return redirect('services:detail', service_id=service.id)
    else:
        form = ServiceForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'services/form.html', context)

@login_required
def service_edit_view(request, service_id):
    """View to handle service editing."""
    service = get_object_or_404(Service, id=service_id)
    
    # Check if user is authorized to edit
    if service.provider != request.user and not request.user.is_staff:
        messages.error(request, 'You are not authorized to edit this service.')
        return redirect('services:detail', service_id=service.id)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            
            # Handle multiple images if provided
            if request.FILES.getlist('additional_images'):
                for image in request.FILES.getlist('additional_images'):
                    ServiceImage.objects.create(service=service, image=image)
            
            messages.success(request, 'Service updated successfully!')
            return redirect('services:detail', service_id=service.id)
    else:
        form = ServiceForm(instance=service)
    
    context = {
        'form': form,
        'service': service,
        'is_create': False,
    }
    
    return render(request, 'services/form.html', context)

@login_required
def service_delete_view(request, service_id):
    """View to handle service deletion."""
    service = get_object_or_404(Service, id=service_id)
    
    # Check if user is authorized to delete
    if service.provider != request.user and not request.user.is_staff:
        messages.error(request, 'You are not authorized to delete this service.')
        return redirect('services:detail', service_id=service.id)
    
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'Service deleted successfully!')
        return redirect('services:list')
    
    context = {
        'service': service,
    }
    
    return render(request, 'services/delete_confirm.html', context)

@login_required
def service_rate_view(request, service_id):
    """HTMX view to add or update a rating for a service."""
    service = get_object_or_404(Service, id=service_id)
    
    # Prevent provider from rating their own service
    if service.provider == request.user:
        return HttpResponse(status=403)
    
    if request.method == 'POST':
        rating_value = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        
        if rating_value and comment:
            # Check if user has already rated this service
            existing_rating = Rating.objects.filter(service=service, user=request.user).first()
            
            if existing_rating:
                # Update existing rating
                existing_rating.value = rating_value
                existing_rating.comment = comment
                existing_rating.save()
                rating = existing_rating
            else:
                # Create new rating
                rating = Rating.objects.create(
                    service=service,
                    user=request.user,
                    value=int(rating_value),
                    comment=comment
                )
            
            context = {
                'rating': rating,
                'new_rating': True,
            }
            
            return render(request, 'services/_rating.html', context)
    
    # Return an empty response if something went wrong
    return HttpResponse(status=400)

@login_required
def service_booking_view(request, service_id):
    """HTMX view to handle booking a service."""
    service = get_object_or_404(Service, id=service_id)
    
    # Prevent provider from booking their own service
    if service.provider == request.user:
        return HttpResponse(status=403)
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        notes = request.POST.get('notes', '')
        
        if date_str and time_str:
            try:
                # Parse date and time
                booking_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
                booking_time = timezone.datetime.strptime(time_str, '%H:%M').time()
                booking_datetime = timezone.datetime.combine(booking_date, booking_time)
                
                # Create booking
                booking = Booking.objects.create(
                    service=service,
                    user=request.user,
                    datetime=booking_datetime,
                    notes=notes,
                    status='pending'
                )
                
                # Return success message
                return HttpResponse(
                    '<div class="alert alert-success">'
                    '<i class="bi bi-check-circle-fill me-2"></i>'
                    'Booking request sent successfully! You will be notified once it is confirmed.'
                    '</div>'
                )
                
            except ValueError:
                return HttpResponse(
                    '<div class="alert alert-danger">'
                    '<i class="bi bi-exclamation-triangle-fill me-2"></i>'
                    'Invalid date or time format.'
                    '</div>',
                    status=400
                )
    
    # Return an empty booking form
    return render(request, 'services/_booking_form.html', {'service': service})

@login_required
def service_upload_media_view(request):
    """HTMX view to handle media uploads for services."""
    if request.method == 'POST' and request.FILES.get('file'):
        file_obj = request.FILES['file']
        service_id = request.POST.get('service_id')
        
        if not service_id:
            return HttpResponse(status=400)
        
        try:
            service = Service.objects.get(id=service_id)
            
            # Check if user is authorized to upload
            if service.provider != request.user and not request.user.is_staff:
                return HttpResponse(status=403)
            
            # Create the service image
            service_image = ServiceImage.objects.create(
                service=service,
                image=file_obj
            )
            
            return JsonResponse({
                'id': service_image.id,
                'url': service_image.image.url,
            })
            
        except Service.DoesNotExist:
            return HttpResponse(status=404)
    
    return HttpResponse(status=400)



def service_add_comment_view(request, service_id): 
    """HTMX view to handle adding comments to a service."""
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        
        if comment_text:
            comment = Comment.objects.create(
                service=service,
                user=request.user,
                text=comment_text
            )
            
            context = {
                'comment': comment,
            }
            
            return render(request, 'services/_comment.html', context)
    
    return HttpResponse(status=400)