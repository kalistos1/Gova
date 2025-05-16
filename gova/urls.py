

# from django.contrib import admin
# from django.urls import path

# urlpatterns = [
#     path('admin/', admin.site.urls),
# ]


"""
URL configuration for abiahub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

URL Patterns:
    - Admin URLs: /admin/
    - Web routes (HTML templates)
    - API base: /api/
    - Reports app: Included at /api/reports/
    - Proposals app: Included at /api/proposals/
    - Services app: Included at /api/services/
    - Engagement app: Included at /api/engagement/
    - Grants app: Included at /api/grants/
    - Accounts app: Included at /api/accounts/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin URLs
    path('admin/', admin.site.urls),
    
    # Web URLs (HTML templates)
    path('', include('core.urls')),
 

    # Web app routes
    path('reports/', include('reports.web_urls', namespace='reports')),
    path('proposals/', include('proposals.web_urls', namespace='proposals')),
    path('services/', include('services.web_urls', namespace='services')),
    # path('grants/', include('grants.web_urls', namespace='grants')),
    path('accounts/', include('accounts.web_urls', namespace='accounts')),
    
    # API URLs
    path('api/reports/', include('reports.urls', namespace='api_reports')),
    path('api/proposals/', include('proposals.urls', namespace='api_proposals')),
    path('api/services/', include('services.urls', namespace='api_services')),
    path('api/engagement/', include('engagement.urls', namespace='api_engagement')),
    # path('api/grants/', include('grants.urls', namespace='api_grants')),
    path('api/accounts/', include('accounts.urls', namespace='api_accounts')),
    path('api/', include('api.urls', namespace='api')), 
    # path('__debug__/', include('debug_toolbar.urls')),
    
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
