# users/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Roles

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or getattr(u, "role", None) == Roles.ADMIN))

class HasRole(BasePermission):
    """
    Usage: in a view, set: required_roles = {Roles.PROCESS, Roles.CTO}
           and include permission_classes = [HasRole]
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        required = getattr(view, "required_roles", None)
        if not required:
            # default: allow read-only to authenticated
            return request.method in SAFE_METHODS
        return (user.is_superuser 
                or getattr(user, "role", None) in required)

# Helper decorators (optional)
def require_roles(*allowed):
    def wrapper(view_cls):
        setattr(view_cls, "required_roles", set(allowed))
        return view_cls
    return wrapper
