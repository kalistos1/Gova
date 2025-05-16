from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'kiosks', views.KioskViewSet)
router.register(r'operators', views.OperatorViewSet)
router.register(r'sync-logs', views.SyncLogViewSet, basename='synclog')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.AdminDashboardView.as_view(), name='admin-dashboard-stats'),
    path('sync-stats/', views.SyncStatsView.as_view(), name='admin-sync-stats'),
] 