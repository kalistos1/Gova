from rest_framework import permissions

class IsStateOfficial(permissions.BasePermission):
    """Allow access only to state officials.
    
    This permission class checks if the authenticated user has the
    is_state_official flag set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user is a state official.
        
        Args:
            request: HTTP request object.
            view: View being accessed.
            
        Returns:
            bool: True if user is authenticated and is a state official.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_state_official
        )

class IsLgaOfficial(permissions.BasePermission):
    """Allow access only to LGA officials.
    
    This permission class checks if the authenticated user has the
    is_lga_official flag set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user is an LGA official.
        
        Args:
            request: HTTP request object.
            view: View being accessed.
            
        Returns:
            bool: True if user is authenticated and is an LGA official.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_lga_official
        )

class IsStateOrLgaOfficial(permissions.BasePermission):
    """Allow access to both state and LGA officials.
    
    This permission class checks if the authenticated user has either
    the is_state_official or is_lga_official flag set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user is either a state or LGA official.
        
        Args:
            request: HTTP request object.
            view: View being accessed.
            
        Returns:
            bool: True if user is authenticated and is either a state or LGA official.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_state_official or request.user.is_lga_official)
        ) 
        
class IsAdminUser(permissions.BasePermission):      
    """Allow access only to admin users.
    
    This permission class checks if the authenticated user has the
    is_admin flag set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user is an admin.
        
        Args:
            request: HTTP request object.
            view: View being accessed.
            
        Returns:
            bool: True if user is authenticated and is an admin.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_admin
        )
        
class IsKioskOperator(permissions.BasePermission):
    """Allow access only to kiosk operators.
    
    This permission class checks if the authenticated user has the
    is_kiosk_operator flag set to True.
    """
    
    def has_permission(self, request, view):
        """Check if user is a kiosk operator.
        
        Args:
            request: HTTP request object.
            view: View being accessed.
            
        Returns:
            bool: True if user is authenticated and is a kiosk operator.
        """
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_kiosk_operator
        )