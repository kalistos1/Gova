from django.db import models
# from django.contrib.gis.db import models as gis_models
import uuid

# Abstract base model for auditing and soft deletes
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Soft delete
    created_by = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL, related_name='%(class)s_created')
    updated_by = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL, related_name='%(class)s_updated')

    class Meta:
        abstract = True

# Location model for LGAs and wards
class Location(BaseModel):
    name = models.CharField(max_length=100)  # e.g., Aba South, Ohafia
    type = models.CharField(max_length=20, choices=[('LGA', 'LGA'), ('Ward', 'Ward')])
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    # coordinates = gis_models.PointField(null=True, blank=True)
    coordinates = models.FloatField(
        null=True,
        blank=True,
        help_text=('Geographic location of the reported issue (latitude, longitude)')
    )

    class Meta:
        indexes = [
            models.Index(fields=['name', 'type']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"


class LGA(BaseModel):
    """Model for Local Government Areas (LGAs).
    
    Attributes:
        name (str): Name of the LGA.
        coordinates (PointField): Geographical coordinates of the LGA.
    """
    name = models.CharField(max_length=100)
    # coordinates = gis_models.PointField(null=True, blank=True)
    coordinates = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name
# Wards model for wards within LGAs 

class Ward(BaseModel):  
    """Model for Wards within LGAs.
    
    Attributes:
        name (str): Name of the ward.
        lga (LGA): The LGA to which the ward belongs.
        coordinates (PointField): Geographical coordinates of the ward.
    """
    name = models.CharField(max_length=100)
    lga = models.ForeignKey(LGA, on_delete=models.CASCADE, related_name='wards')
    # coordinates = gis_models.PointField(null=True, blank=True)
    coordinates = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['lga']),
        ]

    def __str__(self):
        return self.name

    

# Landmark model for specific locations
class Landmark(BaseModel):
    name = models.CharField(max_length=100)  # e.g., "Ariaria Market Stall 5"
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='landmarks')
    # coordinates = gis_models.PointField(null=True, blank=True)
    coordinates  = models.FloatField(
        null=True,
        blank=True,
        help_text=('Geographic location of the reported issue (latitude, longitude)')
    )
    class Meta:
        indexes = [
            models.Index(fields=['name', 'location']),
            models.Index(fields=['coordinates']),
        ]

    def __str__(self):
        return self.name

# Audit log for tracking actions
class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=100)  # e.g., "Report Submitted"
    entity = models.CharField(max_length=50)  # e.g., "Report"
    entity_id = models.UUIDField()
    details = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'entity', 'entity_id']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.action} on {self.entity} ({self.timestamp})"
# proposals/models.py
from django.db import models

class Reward(models.Model):  # Adjust based on your actual model
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='proposal_rewards'  # Unique related_name
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='proposal_rewards_created'  # Unique related_name
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='proposal_rewards_updated'  # Unique related_name
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    action_type = models.CharField(max_length=20)
    reference_id = models.UUIDField()
    reference_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default='PENDING')
    processed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'action_type']),
            models.Index(fields=['reference_id', 'reference_type']),
            models.Index(fields=['status']),
        ]
    
    
class Kiosk(BaseModel):
    """Model for tracking kiosks in the system.
    
    Attributes:
        name (str): Name of the kiosk.
        location (Location): Location of the kiosk.
        coordinates (PointField): Geographical coordinates of the kiosk.
        status (str): Status of the kiosk (active, inactive).
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]
    
    name = models.CharField(max_length=100)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='kiosks')
    # coordinates = gis_models.PointField(null=True, blank=True)
    coordinates  = models.FloatField(
        null=True,
        blank=True,
        help_text=('Geographic location of the reported issue (latitude, longitude)')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['location']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name
    
    
    
class Operator(models.Model):
    name = models.CharField(max_length=100)
    assigned_kiosks = models.ManyToManyField('Kiosk', related_name='operators')
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='operator_profile')

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            # models.Index(fields=['kiosk']),
        ]

    def __str__(self):
        return self.name
    
    
    

    
class Synclog(models.Model):
    """Model for tracking synchronization logs.
    
    Attributes:
        user (User): The user who performed the sync.
        action (str): Action performed during sync.
        status (str): Status of the sync (success, failure).
        details (JSONField): Additional details about the sync.
        timestamp (DateTime): When the sync occurred.
    """
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='sync_logs')
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    details = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['status']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.action} - {self.status} ({self.timestamp})"