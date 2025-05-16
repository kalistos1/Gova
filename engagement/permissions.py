from rest_framework import permissions

class IsStateOfficial(permissions.BasePermission):
    """Custom permission to only allow state officials to access the view.
    
    This permission class checks if the authenticated user has the
    is_state_official attribute set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user has permission to access the view.
        
        Args:
            request: The request object.
            view: The view being accessed.
            
        Returns:
            bool: True if user is authenticated and is a state official,
                  False otherwise.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'is_state_official', False)
        ) 