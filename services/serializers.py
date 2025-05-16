from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Service, ServiceRequest
from core.models import Location, Landmark


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for Service model with camelCase field names."""
    
    serviceId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Service
        fields = [
            'serviceId', 'name', 'description', 'category',
            'basePrice', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['serviceId', 'createdAt', 'updatedAt']


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location model with camelCase field names."""
    
    locationId = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = Location
        fields = ['locationId', 'name', 'latitude', 'longitude']


class LandmarkSerializer(serializers.ModelSerializer):
    """Serializer for Landmark model with camelCase field names."""
    
    landmarkId = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = Landmark
        fields = ['landmarkId', 'name', 'description']


class ServiceRequestSerializer(serializers.ModelSerializer):
    """Serializer for ServiceRequest model with camelCase field names."""
    
    requestId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    service = ServiceSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    landmark = LandmarkSerializer(read_only=True)
    userName = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = [
            'requestId', 'service', 'location', 'landmark', 'amount',
            'status', 'paymentStatus', 'paymentReference', 'paymentLink',
            'userName', 'createdAt', 'updatedAt'
        ]
        read_only_fields = [
            'requestId', 'service', 'location', 'landmark', 'userName',
            'createdAt', 'updatedAt', 'paymentStatus', 'paymentReference',
            'paymentLink'
        ]

    def get_userName(self, obj):
        """Get the full name of the user who made the request."""
        return obj.user.get_full_name() or obj.user.username
    
class ServiceRequestCreateSerializer(serializers.ModelSerializer):  
    """Serializer for creating a ServiceRequest with camelCase field names."""
    
    serviceId = serializers.UUIDField(source='service.id')
    locationId = serializers.UUIDField(source='location.id')
    landmarkId = serializers.UUIDField(source='landmark.id')

    class Meta:
        model = ServiceRequest
        fields = [
            'serviceId', 'locationId', 'landmarkId', 'amount', 'status',
            'paymentStatus', 'paymentReference', 'paymentLink'
        ]
        read_only_fields = ['status', 'paymentStatus', 'paymentReference', 'paymentLink']
        
class ServiceRequestUpdateSerializer(serializers.ModelSerializer):  
    """Serializer for updating a ServiceRequest with camelCase field names."""
    
    serviceId = serializers.UUIDField(source='service.id', required=False)
    locationId = serializers.UUIDField(source='location.id', required=False)
    landmarkId = serializers.UUIDField(source='landmark.id', required=False)

    class Meta:
        model = ServiceRequest
        fields = [
            'serviceId', 'locationId', 'landmarkId', 'amount', 'status',
            'paymentStatus', 'paymentReference', 'paymentLink'
        ]
        read_only_fields = ['status', 'paymentStatus', 'paymentReference', 'paymentLink']