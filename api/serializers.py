from rest_framework import serializers
from django.utils import timezone

class VersionedSerializer(serializers.ModelSerializer):
    """Base serializer class with versioning support."""
    
    def __init__(self, *args, **kwargs):
        """Initialize serializer with version awareness."""
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'version'):
            self.version = request.version
        else:
            self.version = 'v1'  # Default version
            
    def get_field_names(self, declared_fields, info):
        """Get field names based on API version."""
        fields = super().get_field_names(declared_fields, info)
        
        # Version-specific field exclusions
        if self.version == 'v1':
            # Remove fields not available in v1
            fields = [f for f in fields if not f.endswith('_v2')]
        elif self.version == 'v2':
            # Remove v1-specific fields and update v2 field names
            fields = [
                f[:-3] if f.endswith('_v2') else f
                for f in fields
                if not f.endswith('_v1')
            ]
            
        return fields
        
    def to_representation(self, instance):
        """Convert instance to JSON-serializable format."""
        data = super().to_representation(instance)
        
        # Version-specific data transformations
        if self.version == 'v2':
            # Add version-specific metadata
            data['_meta'] = {
                'version': 'v2',
                'deprecated': False,
                'sunset_date': None
            }
            
        return data
        
    def validate(self, data):
        """Validate data based on version requirements."""
        validated_data = super().validate(data)
        
        # Version-specific validation
        if self.version == 'v2':
            # Add stricter validation for v2
            self.validate_v2(validated_data)
            
        return validated_data
        
    def validate_v2(self, data):
        """Additional validation for v2 API."""
        pass  # To be implemented by child classes 

class BaseSerializer(serializers.ModelSerializer):
    """Base serializer class with enhanced validation and metadata."""
    
    def to_representation(self, instance):
        """Convert instance to JSON-serializable format."""
        data = super().to_representation(instance)
        
        # Add useful metadata
        data['_meta'] = {
            'timestamp': timezone.now().isoformat(),
            'type': instance.__class__.__name__
        }
        
        return data
        
    def validate(self, data):
        """Enhanced validation with better error handling."""
        try:
            validated_data = super().validate(data)
            
            # Add enhanced validation here
            self.validate_enhanced(validated_data)
            
            return validated_data
        except serializers.ValidationError as e:
            # Add more context to validation errors
            raise serializers.ValidationError({
                'errors': e.detail,
                'field_types': {
                    field.field_name: field.__class__.__name__
                    for field in self._writable_fields
                },
                'help_text': {
                    field.field_name: field.help_text
                    for field in self._writable_fields
                    if hasattr(field, 'help_text') and field.help_text
                }
            })
            
    def validate_enhanced(self, data):
        """Additional validation with enhanced security checks.
        To be implemented by child classes for specific validation rules.
        """
        pass 