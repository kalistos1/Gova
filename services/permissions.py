from rest_framework import permissions

class IsStateOfficial(permissions.BasePermission):
    """Allow access only to State officials."""
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'is_state_official') and
            request.user.is_state_official
        ) 