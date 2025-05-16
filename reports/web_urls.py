from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Report listing and search
    path('', views.reports_list_view, name='list'),
    path('search/', views.reports_search_view, name='search'),
    
    # Report CRUD operations
    path('create/', views.report_create_view, name='create'),
    path('<uuid:report_id>/', views.report_detail_view, name='detail'),
    path('<uuid:report_id>/edit/', views.report_edit_view, name='edit'),
    path('<uuid:report_id>/delete/', views.report_delete_view, name='delete'),
    
    # Report actions
    path('<uuid:report_id>/comment/', views.report_add_comment_view, name='add_comment'),
    path('<uuid:report_id>/support/', views.report_support_view, name='support'),
    path('<uuid:report_id>/update-status/', views.report_update_status_view, name='update_status'),
    
    # Report media
    path('upload-media/', views.report_upload_media_view, name='upload_media'),
] 