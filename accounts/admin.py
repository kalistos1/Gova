from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""
    
    list_display = [
        'email', 'get_full_name', 'is_state_official', 'is_lga_official',
        'department', 'position', 'is_active', 'date_joined'
    ]
    list_filter = [
        'is_state_official', 'is_lga_official', 'is_active',
        'is_staff', 'date_joined'
    ]
    search_fields = [
        'email', 'first_name', 'last_name', 'phone_number',
        'department', 'position'
    ]
    ordering = ['-date_joined']
    
    # Fields shown in the user detail view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'phone_number')
        }),
        (_('Official info'), {
            'fields': (
                'is_state_official', 'is_lga_official',
                'department', 'position'
            )
        }),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    # Fields shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2', 'first_name',
                'last_name', 'phone_number', 'is_state_official',
                'is_lga_official', 'department', 'position'
            )
        }),
    )
    
    def get_full_name(self, obj):
        """Get formatted full name."""
        return obj.get_full_name() or '-'
    get_full_name.short_description = _('Full name')
    get_full_name.admin_order_field = 'first_name'
