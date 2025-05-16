from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from api.permissions import IsAdminUser
from services.models import Kiosk, SyncLog
from .serializers import (
    DashboardStatsSerializer,
    KioskSerializer,
    OperatorSerializer,
    SyncLogSerializer,
    SyncStatsSerializer
)

User = get_user_model()

class AdminDashboardView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = DashboardStatsSerializer

    def get_object(self):
        # Calculate dashboard statistics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get kiosk stats
        total_kiosks = Kiosk.objects.count()
        active_kiosks = Kiosk.objects.filter(is_active=True).count()
        
        # Get operator stats
        total_operators = User.objects.filter(groups__name='Operators').count()
        active_operators = User.objects.filter(groups__name='Operators', is_active=True).count()
        
        # Get sync stats
        recent_syncs = SyncLog.objects.filter(created_at__gte=thirty_days_ago)
        total_syncs = recent_syncs.count()
        successful_syncs = recent_syncs.filter(status='completed').count()
        sync_success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
        avg_sync_time = recent_syncs.filter(status='completed').aggregate(
            avg_time=Avg('duration')
        )['avg_time'] or 0

        # Get sync success rate over time
        sync_success_over_time = []
        for i in range(30):
            date = timezone.now() - timedelta(days=i)
            day_syncs = recent_syncs.filter(
                created_at__date=date.date()
            )
            day_total = day_syncs.count()
            day_success = day_syncs.filter(status='completed').count()
            success_rate = (day_success / day_total * 100) if day_total > 0 else 0
            sync_success_over_time.append({
                'date': date.date(),
                'successRate': round(success_rate, 2)
            })

        # Get sync status distribution
        status_distribution = recent_syncs.values('status').annotate(
            value=Count('id')
        ).values('status', 'value')

        # Get sync duration by kiosk
        sync_duration_by_kiosk = recent_syncs.filter(
            status='completed'
        ).values('kiosk__name').annotate(
            duration=Avg('duration')
        ).values('name', 'duration')

        return {
            'totalKiosks': total_kiosks,
            'activeKiosks': active_kiosks,
            'totalOperators': total_operators,
            'activeOperators': active_operators,
            'syncSuccessRate': round(sync_success_rate, 2),
            'avgSyncTime': round(avg_sync_time, 2),
            'syncSuccessOverTime': sync_success_over_time,
            'syncStatusDistribution': status_distribution,
            'syncDurationByKiosk': sync_duration_by_kiosk
        }

class KioskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Kiosk.objects.all()
    serializer_class = KioskSerializer

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        kiosk_ids = request.data.get('kioskIds', [])
        Kiosk.objects.filter(id__in=kiosk_ids).update(is_active=True)
        return Response({'status': 'success'})

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        kiosk_ids = request.data.get('kioskIds', [])
        Kiosk.objects.filter(id__in=kiosk_ids).update(is_active=False)
        return Response({'status': 'success'})

    @action(detail=False, methods=['post'])
    def bulk_sync(self, request):
        kiosk_ids = request.data.get('kioskIds', [])
        kiosks = Kiosk.objects.filter(id__in=kiosk_ids)
        for kiosk in kiosks:
            SyncLog.objects.create(
                kiosk=kiosk,
                sync_type='manual',
                status='pending'
            )
        return Response({'status': 'success'})

class OperatorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = User.objects.filter(groups__name='Operators')
    serializer_class = OperatorSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        user.groups.add('Operators')
        return user

class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = SyncLog.objects.all().order_by('-created_at')
    serializer_class = SyncLogSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        time_range = self.request.query_params.get('time_range', '7d')
        
        if time_range == '24h':
            start_date = timezone.now() - timedelta(days=1)
        elif time_range == '7d':
            start_date = timezone.now() - timedelta(days=7)
        elif time_range == '30d':
            start_date = timezone.now() - timedelta(days=30)
        elif time_range == '90d':
            start_date = timezone.now() - timedelta(days=90)
        else:
            start_date = timezone.now() - timedelta(days=7)

        return queryset.filter(created_at__gte=start_date)

class SyncStatsView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = SyncStatsSerializer

    def get_object(self):
        time_range = self.request.query_params.get('time_range', '7d')
        
        if time_range == '24h':
            start_date = timezone.now() - timedelta(days=1)
        elif time_range == '7d':
            start_date = timezone.now() - timedelta(days=7)
        elif time_range == '30d':
            start_date = timezone.now() - timedelta(days=30)
        elif time_range == '90d':
            start_date = timezone.now() - timedelta(days=90)
        else:
            start_date = timezone.now() - timedelta(days=7)

        syncs = SyncLog.objects.filter(created_at__gte=start_date)
        total_syncs = syncs.count()
        successful_syncs = syncs.filter(status='completed').count()
        failed_syncs = syncs.filter(status='failed').count()
        success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
        avg_duration = syncs.filter(status='completed').aggregate(
            avg_time=Avg('duration')
        )['avg_time'] or 0

        # Get success rate over time
        success_rate_over_time = []
        days = 7 if time_range == '7d' else 30 if time_range == '30d' else 90 if time_range == '90d' else 1
        for i in range(days):
            date = timezone.now() - timedelta(days=i)
            day_syncs = syncs.filter(created_at__date=date.date())
            day_total = day_syncs.count()
            day_success = day_syncs.filter(status='completed').count()
            success_rate = (day_success / day_total * 100) if day_total > 0 else 0
            success_rate_over_time.append({
                'date': date.date(),
                'successRate': round(success_rate, 2)
            })

        # Get status distribution
        status_distribution = syncs.values('status').annotate(
            value=Count('id')
        ).values('status', 'value')

        # Get duration by kiosk
        duration_by_kiosk = syncs.filter(
            status='completed'
        ).values('kiosk__name').annotate(
            duration=Avg('duration')
        ).values('name', 'duration')

        return {
            'totalSyncs': total_syncs,
            'successRate': round(success_rate, 2),
            'failedSyncs': failed_syncs,
            'avgDuration': round(avg_duration, 2),
            'successRateOverTime': success_rate_over_time,
            'statusDistribution': status_distribution,
            'durationByKiosk': duration_by_kiosk
        } 