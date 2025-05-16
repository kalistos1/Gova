from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Proposal, Vote
from core.models import Location, Landmark


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


class ProposalSerializer(serializers.ModelSerializer):
    """Serializer for Proposal model with camelCase field names."""
    
    proposalId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    location = LocationSerializer(read_only=True)
    landmark = LandmarkSerializer(read_only=True)
    votes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            'proposalId', 'title', 'description', 'status', 'category',
            'location', 'landmark', 'votes', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['proposalId', 'votes', 'createdAt', 'updatedAt']


class VoteSerializer(serializers.ModelSerializer):
    """Serializer for Vote model with camelCase field names."""
    
    voteId = serializers.UUIDField(source='id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Vote
        fields = [
            'voteId', 'proposal', 'user', 'value', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['voteId', 'createdAt', 'updatedAt']
        
        
class ProposalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a Proposal with camelCase field names."""
    
    locationId = serializers.UUIDField(source='location.id')
    landmarkId = serializers.UUIDField(source='landmark.id')

    class Meta:
        model = Proposal
        fields = [
            'title', 'description', 'status', 'category',
            'locationId', 'landmarkId'
        ]
        extra_kwargs = {
            'status': {'default': Proposal.Status.DRAFT},
            'category': {'default': Proposal.Category.OTHER}
        }