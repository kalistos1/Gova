from django.urls import path
from . import views

app_name = 'engagement'

urlpatterns = [
    # Message endpoints
    path('messages/', views.message_list, name='message-list'),
    path('messages/create/', views.message_create, name='message-create'),
    path('messages/<uuid:pk>/responses/', views.message_response, name='message-response'),
    
    # Notification endpoints
    path('notifications/create/', views.notification_create, name='notification-create'),
    
    # Recipient group endpoints
    path('recipient-groups/', views.recipient_group_list, name='recipient-group-list'),
]
