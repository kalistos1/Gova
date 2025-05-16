from django.urls import path
from . import views

app_name = 'proposals'

urlpatterns = [
    # Proposal listing and search
    path('', views.proposals_list_view, name='list'),
    path('search/', views.proposals_search_view, name='search'),
    
    # Proposal CRUD operations
    path('create/', views.proposal_create_view, name='create'),
    path('<uuid:proposal_id>/', views.proposal_detail_view, name='detail'),
    path('<uuid:proposal_id>/edit/', views.proposal_edit_view, name='edit'),
    path('<uuid:proposal_id>/delete/', views.proposal_delete_view, name='delete'),
    
    # Proposal actions
    path('<uuid:proposal_id>/comment/', views.proposal_add_comment_view, name='add_comment'),
    path('<uuid:proposal_id>/vote/', views.proposal_vote_view, name='vote'),
    path('<uuid:proposal_id>/update-status/', views.proposal_update_status_view, name='update_status'),
    
    # Proposal attachments
    path('upload-attachment/', views.proposal_upload_attachment_view, name='upload_attachment'),
] 