from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Service listing and search
    path('', views.services_list_view, name='list'),
    path('search/', views.services_search_view, name='search'),
    
    # Service CRUD operations
    path('create/', views.service_create_view, name='create'),
    path('<uuid:service_id>/', views.service_detail_view, name='detail'),
    path('<uuid:service_id>/edit/', views.service_edit_view, name='edit'),
    path('<uuid:service_id>/delete/', views.service_delete_view, name='delete'),
    
    # Service actions
    path('<uuid:service_id>/comment/', views.service_add_comment_view, name='add_comment'),
    path('<uuid:service_id>/rate/', views.service_rate_view, name='rate'),
    path('<uuid:service_id>/booking/', views.service_booking_view, name='booking'),
    
    # Service media
    path('upload-media/', views.service_upload_media_view, name='upload_media'),
] 