from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Service endpoints
    path('services/', views.service_list, name='service-list'),
    path('services/<uuid:pk>/', views.service_detail, name='service-detail'),
    
    # Service request endpoints
    path('service-requests/', views.service_request_list, name='service-request-list'),
    path('service-requests/create/', views.service_request_create, name='service-request-create'),
    path('service-requests/<uuid:pk>/update/', views.service_request_update, name='service-request-update'),
]
