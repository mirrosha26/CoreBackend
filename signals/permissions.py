from rest_framework import permissions


class IsAdminUserWithToken(permissions.BasePermission):
    """
    Разрешение для доступа к серверному API.
    
    Требует:
    - Аутентифицированного пользователя
    - Статуса администратора (is_staff)
    - Валидного токена аутентификации
    
    Используется для защиты серверного API от несанкционированного доступа.
    """
    
    def has_permission(self, request, view):
        """
        Проверяет, имеет ли пользователь разрешение на доступ.
        
        Args:
            request: HTTP запрос
            view: View, к которому запрашивается доступ
            
        Returns:
            bool: True если пользователь аутентифицирован, is_staff и имеет токен
        """
        return bool(
            request.user 
            and request.user.is_authenticated
            and request.user.is_staff 
            and request.auth
        )