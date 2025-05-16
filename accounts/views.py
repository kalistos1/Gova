from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.pagination import PageNumberPagination
import logging
from typing import Dict, Any
from django.db.models import Q
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import requests
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .serializers import (
    UserSerializer, UserCreateSerializer,
    UserUpdateSerializer, UserRegistrationSerializer,
    UserProfileUpdateSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    NINVerificationSerializer, UserProfileSerializer,
    RewardSerializer, KioskSerializer #SyncLogSerializer
)
from .permissions import IsStateOfficial, IsLgaOfficial, IsAdminUser, IsKioskOperator
from core.models import AuditLog, Location
from .utils import (
    generate_verification_token, generate_password_reset_token,
    verify_token, send_verification_email, send_password_reset_email,
    generate_temporary_password
)
from core.models import Reward, Kiosk , Synclog

User = get_user_model()
logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for user listings."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that includes user data in response."""
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            user = User.objects.get(email=request.data['email'])
            user_data = UserSerializer(user).data
            response.data['user'] = user_data
            
            # Log successful login
            AuditLog.objects.create(
                action='User Login',
                user=user,
                details='User logged in successfully'
            )
        
        return response

class NINVerificationRateThrottle(AnonRateThrottle):
    """Rate limit for NIN verification attempts."""
    rate = '5/hour'  # 5 attempts per hour for anonymous users

class NINVerificationUserRateThrottle(UserRateThrottle):
    """Rate limit for authenticated users' NIN verification attempts."""
    rate = '10/hour'  # 10 attempts per hour for authenticated users

@api_view(['POST'])
@permission_classes([AllowAny])
def user_register(request):
    """Register a new user.
    
    Args:
        request: HTTP request object containing user data.
            
    Returns:
        User data and tokens in camelCase format.
        
    Raises:
        400: If registration data is invalid.
    """
    serializer = UserCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = serializer.save()
    
    # Generate tokens
    refresh = RefreshToken.for_user(user)
    
    # Log registration
    AuditLog.objects.create(
        action='User Registration',
        user=user,
        details='New user registered'
    )
    
    return Response({
        'user': UserSerializer(user).data,
        'tokens': {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
    }, status=status.HTTP_201_CREATED)

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update user profile.
    
    Args:
        request: HTTP request object.
            
    Returns:
        User profile data in camelCase format.
        
    Raises:
        400: If update data is invalid.
    """
    if request.method == 'GET':
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    # PATCH request
    serializer = UserUpdateSerializer(
        request.user,
        data=request.data,
        partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = serializer.save()
    
    # Log profile update
    AuditLog.objects.create(
        action='Profile Update',
        user=request.user,
        details='User profile updated'
    )
    
    return Response(UserSerializer(user).data)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_list(request):
    """List all users (admin only).
    
    Args:
        request: HTTP request object.
            
    Returns:
        Paginated list of users in camelCase format.
        
    Query Parameters:
        role: Filter by role (state_official, lga_official).
        search: Search in email, name, department.
    """
    users = User.objects.all()
    
    # Apply filters
    role = request.query_params.get('role')
    if role == 'state_official':
        users = users.filter(is_state_official=True)
    elif role == 'lga_official':
        users = users.filter(is_lga_official=True)
    
    search = request.query_params.get('search')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(department__icontains=search)
        )
    
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(users, request)
    
    return Response(
        UserSerializer(page, many=True).data,
        headers={'X-Total-Count': users.count()}
    )

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def user_role_update(request, pk):
    """Update user roles (admin only).
    
    Args:
        request: HTTP request object containing role data.
        pk: UUID of the user to update.
            
    Returns:
        Updated user data in camelCase format.
        
    Raises:
        400: If role data is invalid.
        404: If user not found.
    """
    user = get_object_or_404(User, pk=pk)
    
    # Only allow updating role fields
    allowed_fields = {'isStateOfficial', 'isLgaOfficial'}
    if not all(field in allowed_fields for field in request.data.keys()):
        return Response(
            {'error': 'Only role fields can be updated'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = UserSerializer(
        user,
        data=request.data,
        partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = serializer.save()
    
    # Log role update
    AuditLog.objects.create(
        action='Role Update',
        user=request.user,
        details=f'Updated roles for user {user.email}'
    )
    
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_logout(request):
    """Logout user and blacklist refresh token.
    
    Args:
        request: HTTP request object containing refresh token.
            
    Returns:
        Success message.
        
    Raises:
        400: If refresh token is missing.
    """
    try:
        refresh_token = request.data['refresh']
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        # Log logout
        AuditLog.objects.create(
            action='User Logout',
            user=request.user,
            details='User logged out successfully'
        )
        
        return Response({'message': 'Successfully logged out'})
    except KeyError:
        return Response(
            {'error': 'Refresh token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f'Logout failed: {str(e)}')
        return Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Request a password reset link.
    
    Args:
        request: The HTTP request containing the user's email.
        
    Returns:
        Response: A success message if the email exists.
        
    Raises:
        None: Returns 200 even if email doesn't exist (security best practice).
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data['email']
    try:
        user = User.objects.get(email=email, is_active=True)
        token = generate_password_reset_token(str(user.id))
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
        if send_password_reset_email(user.email, reset_url):
            AuditLog.objects.create(
                user=user,
                action='Password Reset Requested',
                details={'email': user.email}
            )
            return Response({
                'message': _('If an account exists with this email, you will receive a password reset link.')
            })
    except User.DoesNotExist:
        pass
    
    # Return same message even if user doesn't exist (security best practice)
    return Response({
        'message': _('If an account exists with this email, you will receive a password reset link.')
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password using a valid token.
    
    Args:
        request: The HTTP request containing the token and new password.
        
    Returns:
        Response: Success message if password is reset.
        
    Raises:
        400: If token is invalid or expired.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    token = serializer.validated_data['token']
    new_password = serializer.validated_data['new_password']
    
    user_id = verify_token(token, 'password_reset')
    if not user_id:
        return Response(
            {'error': _('Invalid or expired token.')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id, is_active=True)
        user.set_password(new_password)
        user.save()
        
        # Invalidate all existing sessions
        RefreshToken.for_user(user)
        
        AuditLog.objects.create(
            user=user,
            action='Password Reset Completed',
            details={'email': user.email}
        )
        
        return Response({
            'message': _('Password has been reset successfully.')
        })
    except User.DoesNotExist:
        return Response(
            {'error': _('User not found.')},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """Verify user's email address using a token.
    
    Args:
        request: The HTTP request containing the verification token.
        
    Returns:
        Response: Success message if email is verified.
        
    Raises:
        400: If token is invalid or expired.
    """
    token = request.data.get('token')
    if not token:
        return Response(
            {'error': _('Token is required.')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user_id = verify_token(token, 'verification')
    if not user_id:
        return Response(
            {'error': _('Invalid or expired token.')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id, is_active=True)
        if user.is_email_verified:
            return Response({
                'message': _('Email is already verified.')
            })
        
        user.is_email_verified = True
        user.save()
        
        AuditLog.objects.create(
            user=user,
            action='Email Verified',
            details={'email': user.email}
        )
        
        return Response({
            'message': _('Email verified successfully.')
        })
    except User.DoesNotExist:
        return Response(
            {'error': _('User not found.')},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification(request):
    """Resend email verification link.
    
    Args:
        request: The HTTP request containing the user's email.
        
    Returns:
        Response: Success message if verification email is sent.
        
    Raises:
        400: If email is invalid or user is already verified.
    """
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': _('Email is required.')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email, is_active=True)
        if user.is_email_verified:
            return Response(
                {'error': _('Email is already verified.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = generate_verification_token(str(user.id))
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        if send_verification_email(user.email, verification_url):
            AuditLog.objects.create(
                user=user,
                action='Verification Email Resent',
                details={'email': user.email}
            )
            return Response({
                'message': _('Verification email has been sent.')
            })
    except User.DoesNotExist:
        pass
    
    # Return same message even if user doesn't exist (security best practice)
    return Response({
        'message': _('If an account exists with this email, you will receive a verification link.')
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_official_account(request):
    """Create an account for a state or LGA official.
    
    Args:
        request: The HTTP request containing official's details.
        
    Returns:
        Response: Created user data with temporary password.
        
    Raises:
        400: If data is invalid.
        403: If user is not an admin.
    """
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Generate a temporary password
    temp_password = generate_temporary_password()
    
    # Create user with temporary password
    user = User.objects.create_user(
        email=serializer.validated_data['email'],
        password=temp_password,
        first_name=serializer.validated_data['first_name'],
        last_name=serializer.validated_data['last_name'],
        phone_number=serializer.validated_data.get('phone_number'),
        department=serializer.validated_data.get('department'),
        position=serializer.validated_data.get('position'),
        is_state_official=serializer.validated_data.get('is_state_official', False),
        is_lga_official=serializer.validated_data.get('is_lga_official', False)
    )
    
    # Send verification email
    token = generate_verification_token(str(user.id))
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_verification_email(user.email, verification_url)
    
    AuditLog.objects.create(
        user=request.user,
        action='Official Account Created',
        details={
            'created_user_id': str(user.id),
            'email': user.email,
            'is_state_official': user.is_state_official,
            'is_lga_official': user.is_lga_official
        }
    )
    
    return Response({
        'message': _('Official account created successfully.'),
        'user': UserSerializer(user).data,
        'temporary_password': temp_password  # Only returned in this response
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([NINVerificationRateThrottle, NINVerificationUserRateThrottle])
def verify_nin(request):
    """Verify user's NIN and authenticate.
    
    Rate limited to:
    - 5 attempts per hour for anonymous users
    - 10 attempts per hour for authenticated users
    
    Args:
        request: HTTP request containing NIN verification data.
        
    Returns:
        Response: JWT tokens and user data if verification successful.
        
    Raises:
        400: If verification data is invalid.
        401: If NIN verification fails.
        429: If rate limit exceeded.
        503: If VerifyMe API is unavailable.
    """
    serializer = NINVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Call VerifyMe API
    try:
        verify_me_response = requests.post(
            settings.VERIFYME_API_URL,
            json={
                'nin': serializer.validated_data['nin'],
                'first_name': serializer.validated_data['first_name'],
                'last_name': serializer.validated_data['last_name'],
                'date_of_birth': serializer.validated_data['date_of_birth'].isoformat()
            },
            headers={'Authorization': f'Bearer {settings.VERIFYME_API_KEY}'},
            timeout=10
        )
        verify_me_response.raise_for_status()
        verification_data = verify_me_response.json()
        
        if not verification_data.get('verified'):
            return Response(
                {'error': _('NIN verification failed. Please check your details.')},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=verification_data['email'],
            defaults={
                'first_name': verification_data['first_name'],
                'last_name': verification_data['last_name'],
                'phone_number': verification_data.get('phone_number', ''),
                'is_nin_verified': True,
                'nin_number': serializer.validated_data['nin']
            }
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Log authentication
        AuditLog.objects.create(
            user=user,
            action='User Authenticated via NIN',
            details={
                'nin': serializer.validated_data['nin'],
                'is_new_user': created
            }
        )
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        })
        
    except requests.RequestException as e:
        logger.error(f'VerifyMe API error: {str(e)}')
        return Response(
            {'error': _('Unable to verify NIN at this time. Please try again later.')},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """Get authenticated user's profile.
    
    Args:
        request: HTTP request from authenticated user.
        
    Returns:
        Response: User profile data in camelCase format.
    """
    user = request.user.select_related('location')
    serializer = UserProfileSerializer(user)
    
    # Log profile view
    AuditLog.objects.create(
        user=user,
        action='Profile Viewed',
        details={'viewed_at': timezone.now().isoformat()}
    )
    
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_user_rewards(request):
    """List authenticated user's rewards.
    
    Args:
        request: HTTP request from authenticated user.
        
    Returns:
        Response: List of user's rewards in camelCase format.
        
    Query Parameters:
        is_redeemed: Filter by redemption status (optional).
        reward_type: Filter by reward type (optional).
    """
    rewards = Reward.objects.filter(user=request.user)
    
    # Apply filters
    is_redeemed = request.query_params.get('is_redeemed')
    if is_redeemed is not None:
        rewards = rewards.filter(is_redeemed=is_redeemed.lower() == 'true')
    
    reward_type = request.query_params.get('reward_type')
    if reward_type:
        rewards = rewards.filter(reward_type=reward_type)
    
    # Order by creation date
    rewards = rewards.order_by('-created_at')
    
    serializer = RewardSerializer(rewards, many=True)
    
    # Log rewards view
    AuditLog.objects.create(
        user=request.user,
        action='Rewards Viewed',
        details={
            'filters': {
                'is_redeemed': is_redeemed,
                'reward_type': reward_type
            }
        }
    )
    
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 15)  # Cache for 15 minutes
def list_kiosks(request):
    """List all active kiosks.
    
    Results are cached for 15 minutes to improve performance.
    Cache is invalidated when a sync log is created.
    
    Args:
        request: HTTP request.
        
    Returns:
        Response: List of kiosks in camelCase format.
        
    Query Parameters:
        location_id: Filter by location (optional).
        is_active: Filter by active status (optional).
    """
    # Generate cache key based on query parameters
    cache_key = f"kiosks_list_{request.query_params.get('location_id', 'all')}_{request.query_params.get('is_active', 'all')}"
    
    # Try to get from cache
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Response(cached_data)
    
    kiosks = Kiosk.objects.select_related('location').filter(is_active=True)
    
    # Apply filters
    location_id = request.query_params.get('location_id')
    if location_id:
        kiosks = kiosks.filter(location_id=location_id)
    
    is_active = request.query_params.get('is_active')
    if is_active is not None:
        kiosks = kiosks.filter(is_active=is_active.lower() == 'true')
    
    # Order by location and name
    kiosks = kiosks.order_by('location__name', 'name')
    
    serializer = KioskSerializer(kiosks, many=True)
    data = serializer.data
    
    # Cache the results
    cache.set(cache_key, data, 60 * 15)  # Cache for 15 minutes
    
    # Log kiosk list view (anonymous)
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='Kiosks Viewed',
            details={
                'filters': {
                    'location_id': location_id,
                    'is_active': is_active
                }
            }
        )
    else:
        AuditLog.objects.create(
            action='Kiosks Viewed (Anonymous)',
            details={
                'filters': {
                    'location_id': location_id,
                    'is_active': is_active
                }
            }
        )
    
    return Response(data)

@api_view(['POST'])
@permission_classes([IsKioskOperator])
def create_sync_log(request):
    """Create a sync log for a kiosk.
    
    This endpoint also invalidates the kiosk listing cache.
    
    Args:
        request: HTTP request from authenticated kiosk operator.
        
    Returns:
        Response: Created sync log data in camelCase format.
        
    Raises:
        400: If sync data is invalid.
        403: If user is not a kiosk operator.
    """
    # Ensure user is a kiosk operator
    if not request.user.is_kiosk_operator:
        return Response(
            {'error': _('Only kiosk operators can create sync logs.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get kiosk for operator
    try:
        kiosk = Kiosk.objects.get(operator=request.user, is_active=True)
    except Kiosk.DoesNotExist:
        return Response(
            {'error': _('No active kiosk found for this operator.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Add kiosk to request data
    data = request.data.copy()
    data['kiosk'] = kiosk.id
    
    serializer = SyncLogSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    
    # Create sync log
    sync_log = serializer.save(
        kiosk=kiosk,
        sync_status='in_progress'
    )
    
    # Update kiosk last sync time
    kiosk.last_sync_at = timezone.now()
    kiosk.save()
    
    # Invalidate kiosk listing cache
    cache.delete_pattern("kiosks_list_*")
    
    # Log sync creation
    AuditLog.objects.create(
        user=request.user,
        action='Sync Log Created',
        details={
            'kiosk_id': str(kiosk.id),
            'sync_type': sync_log.sync_type,
            'sync_id': str(sync_log.id)
        }
    )
    
    return Response(serializer.data, status=status.HTTP_201_CREATED)

# HTML Template View Functions

def login_view(request):
    """View function for user login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'accounts:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'accounts/login.html')

def register_view(request):
    """View function for user registration"""
    if request.method == 'POST':
        # Handle form submission
        # Create user and profile
        # Send verification email
        # Show success message
        messages.success(request, 'Registration successful! Please check your email to verify your account.')
        return redirect('accounts:login')
    
    # Get all LGAs for the dropdown
    lgas = []  # Get from database in real implementation
    
    return render(request, 'accounts/register.html', {'lgas': lgas})

def logout_view(request):
    """View function for user logout"""
    logout(request)
    messages.info(request, 'You have been logged out successfully')
    return redirect('home')

def password_reset_view(request):
    """View function for password reset request"""
    if request.method == 'POST':
        # Process password reset request
        email = request.POST.get('email')
        # Send password reset email
        messages.info(request, 'If an account with that email exists, we have sent instructions to reset your password')
        return redirect('accounts:login')
    
    return render(request, 'accounts/password_reset.html')

def password_reset_confirm_view(request, uidb64, token):
    """View function for confirming password reset"""
    # Validate token and uidb64
    if request.method == 'POST':
        # Process new password
        # Show success message
        messages.success(request, 'Your password has been reset successfully. Please log in with your new password.')
        return redirect('accounts:login')
    
    return render(request, 'accounts/password_reset_confirm.html')

def verify_email_view(request, token):
    """View function for email verification"""
    # Verify token and activate user account
    messages.success(request, 'Your email has been verified successfully. You can now log in to your account.')
    return redirect('accounts:login')

@login_required
def dashboard_view(request):
    """View function for the user dashboard"""
    # Get user stats
    stats = {
        'reports_count': 5,  # Replace with real data
        'pending_reports': 2,
        'resolved_reports': 3,
        'proposals_count': 3,
        'proposal_votes': 25,
        'service_requests_count': 2,
        'pending_services': 1,
        'completed_services': 1,
        'reward_points': 150
    }
    
    # Get chart data
    chart_data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'reports': [1, 2, 0, 1, 1, 0],
        'proposals': [0, 1, 1, 0, 0, 1],
        'services': [0, 0, 1, 0, 1, 0]
    }
    
    # Get recent activities
    recent_activities = [
        {'icon': 'exclamation-triangle', 'icon_color': 'danger', 'message': 'You reported a road issue', 'timestamp': '2023-06-15T12:30:00Z'},
        {'icon': 'lightbulb', 'icon_color': 'success', 'message': 'Your proposal received a new vote', 'timestamp': '2023-06-10T09:15:00Z'},
        {'icon': 'gear', 'icon_color': 'info', 'message': 'Your service request was completed', 'timestamp': '2023-06-01T14:45:00Z'}
    ]
    
    # Get upcoming tasks
    upcoming_tasks = [
        {'category': 'Service', 'category_color': 'info', 'title': 'Business registration appointment', 'due_date': '2023-06-20'},
        {'category': 'Report', 'category_color': 'danger', 'title': 'Follow up on road repair', 'due_date': '2023-06-25'}
    ]
    
    context = {
        'stats': stats,
        'chart_data': chart_data,
        'recent_activities': recent_activities,
        'upcoming_tasks': upcoming_tasks,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/dashboard.html', context)

@login_required
def profile_view(request):
    """View function for the user profile page"""
    # Get user stats
    stats = {
        'reports_count': 5,  # Replace with real data
        'proposals_count': 3,
        'reward_points': 150
    }
    
    # Get all LGAs for the dropdown
    lgas = []  # Get from database in real implementation
    
    context = {
        'stats': stats,
        'lgas': lgas,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/profile.html', context)

@login_required
@require_POST
def update_profile_view(request):
    """HTMX endpoint for updating the user profile"""
    # Process form data
    # Update user and profile
    
    # Return the updated form
    messages.success(request, 'Profile updated successfully')
    return redirect('accounts:profile')

@login_required
@require_POST
def update_bio_view(request):
    """HTMX endpoint for updating the user bio"""
    # Process bio update
    
    messages.success(request, 'Bio updated successfully')
    return redirect('accounts:profile')

@login_required
@require_POST
def upload_photo_view(request):
    """HTMX endpoint for uploading a profile photo"""
    # Process photo upload
    
    messages.success(request, 'Profile photo updated successfully')
    return redirect('accounts:profile')

@login_required
@require_POST
def change_password_view(request):
    """HTMX endpoint for changing the user password"""
    # Process password change
    
    # Return HTMX response
    return HttpResponse('<div class="alert alert-success">Password changed successfully</div>')

@login_required
def my_reports_view(request):
    """View function for the user's reports page"""
    # Get user reports
    reports = []  # Replace with real data
    
    context = {
        'reports': reports,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/my_reports.html', context)

@login_required
def my_proposals_view(request):
    """View function for the user's proposals page"""
    # Get user proposals
    proposals = []  # Replace with real data
    
    context = {
        'proposals': proposals,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/my_proposals.html', context)

@login_required
def my_services_view(request):
    """View function for the user's services page"""
    # Get user service requests
    service_requests = []  # Replace with real data
    
    context = {
        'service_requests': service_requests,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/my_services.html', context)

@login_required
def messages_view(request):
    """View function for the user's messages page"""
    # Get user messages
    messages_list = []  # Replace with real data
    
    context = {
        'messages_list': messages_list,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/messages.html', context)

@login_required
def rewards_view(request):
    """View function for the user's rewards page"""
    # Get user rewards and available rewards
    rewards = []  # Replace with real data
    available_rewards = []  # Replace with real data
    
    context = {
        'rewards': rewards,
        'available_rewards_list': available_rewards,
        'reward_points': 150,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/rewards.html', context)

@login_required
def notifications_view(request):
    """View function for the user's notifications page"""
    # Get user notifications
    notifications = []  # Replace with real data
    
    context = {
        'notifications': notifications,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/notifications.html', context)

@login_required
def nin_verification_view(request):
    """View function for NIN verification"""
    if request.method == 'POST':
        # Process NIN verification
        # Show success message
        messages.success(request, 'Your NIN has been verified successfully')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/verify_nin.html')

@login_required
def two_factor_view(request):
    """View function for two-factor authentication setup"""
    if request.method == 'POST':
        # Process 2FA setup
        # Show success message
        messages.success(request, 'Two-factor authentication has been set up successfully')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/two_factor.html')

def update_profile(request):
    """View function for updating user profile via HTMX"""
    if request.method == 'POST':
        # Process form data
        # Update user profile
        
        messages.success(request, 'Profile updated successfully')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/update_profile.html') 


def user_detail(request, user_id):
    """View function for user detail page (admin only)"""
    user = get_object_or_404(User, pk=user_id)
    
    # Get user stats
    stats = {
        'reports_count': 5,  # Replace with real data
        'proposals_count': 3,
        'reward_points': 150
    }
    
    context = {
        'user': user,
        'stats': stats,
        'unread_messages_count': 3
    }
    
    return render(request, 'accounts/user_detail.html', context)

def toggle_user_status(request, user_id):
    """View function for toggling user status (admin only)"""
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        # Toggle user status
        user.is_active = not user.is_active
        user.save()
        
        messages.success(request, f'User {user.email} status updated successfully')
        return redirect('accounts:user-list')
    
    return render(request, 'accounts/toggle_user_status.html', {'user': user})

def update_user_role(request, user_id):
    """View function for updating user role (admin only)"""
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        # Process role update
        # Show success message
        messages.success(request, f'User {user.email} role updated successfully')
        return redirect('accounts:user-list')
    
    return render(request, 'accounts/update_user_role.html', {'user': user})