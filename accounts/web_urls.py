from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('verify-email/<token>/', views.verify_email_view, name='verify_email'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # User actions
    path('profile/update/', views.update_profile_view, name='update_profile'),
    path('profile/update-bio/', views.update_bio_view, name='update_bio'),
    path('profile/upload-photo/', views.upload_photo_view, name='upload_photo'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    
    # User activity
    path('my-reports/', views.my_reports_view, name='my_reports'),
    path('my-proposals/', views.my_proposals_view, name='my_proposals'),
    path('my-services/', views.my_services_view, name='my_services'),
    path('messages/', views.messages_view, name='messages'),
    path('rewards/', views.rewards_view, name='rewards'),
    path('notifications/', views.notifications_view, name='notifications'),
    
    # NIN Verification
    path('verify-nin/', views.nin_verification_view, name='verify_nin'),
    
    # Special
    path('two-factor/', views.two_factor_view, name='two_factor'),
] 