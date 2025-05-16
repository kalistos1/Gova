from rest_framework import serializers
from django.contrib.auth import get_user_model
from services.models import Kiosk, SyncLog

User = get_user_model()

class DashboardStatsSerializer(serializers.Serializer):
    totalKiosks = serializers.IntegerField()
    activeKiosks = serializers.IntegerField()
    totalOperators = serializers.IntegerField()
    activeOperators = serializers.IntegerField()
    syncSuccessRate = serializers.FloatField()
    avgSyncTime = serializers.FloatField()
    syncSuccessOverTime = serializers.ListField(
        child=serializers.DictField(
            child=serializers.FloatField()
        )
    )
    syncStatusDistribution = serializers.ListField(
        child=serializers.DictField()
    )
    syncDurationByKiosk = serializers.ListField(
        child=serializers.DictField()
    )

class KioskSerializer(serializers.ModelSerializer):
    locationName = serializers.CharField(source='location.name', read_only=True)
    lastSyncAt = serializers.DateTimeField(source='last_sync.created_at', read_only=True)

    class Meta:
        model = Kiosk
        fields = ['id', 'name', 'location', 'locationName', 'is_active', 'lastSyncAt']
        read_only_fields = ['id']

class OperatorSerializer(serializers.ModelSerializer):
    assignedKiosks = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 
                 'is_active', 'assignedKiosks', 'date_joined']
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def get_assignedKiosks(self, obj):
        return Kiosk.objects.filter(operators=obj).values('id', 'name')

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

class SyncLogSerializer(serializers.ModelSerializer):
    kioskName = serializers.CharField(source='kiosk.name', read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = SyncLog
        fields = ['id', 'kiosk', 'kioskName', 'sync_type', 'status', 
                 'created_at', 'completed_at', 'duration', 'error']
        read_only_fields = ['id', 'created_at', 'completed_at', 'duration']

    def get_duration(self, obj):
        if obj.completed_at and obj.created_at:
            return (obj.completed_at - obj.created_at).total_seconds()
        return None

class SyncStatsSerializer(serializers.Serializer):
    totalSyncs = serializers.IntegerField()
    successRate = serializers.FloatField()
    failedSyncs = serializers.IntegerField()
    avgDuration = serializers.FloatField()
    successRateOverTime = serializers.ListField(
        child=serializers.DictField(
            child=serializers.FloatField()
        )
    )
    statusDistribution = serializers.ListField(
        child=serializers.DictField()
    )
    durationByKiosk = serializers.ListField(
        child=serializers.DictField()
    ) 