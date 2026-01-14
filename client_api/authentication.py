from rest_framework import authentication
from rest_framework import exceptions
from django.utils import timezone
from .models import ClientAPIToken


class ClientAPITokenAuthentication(authentication.BaseAuthentication):
    """
    Аутентификация на основе постоянных токенов клиентского API.
    Токен передается в заголовке Authorization: Token <token>
    """
    keyword = 'Token'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None

        try:
            # Проверяем формат заголовка: "Token <token>"
            parts = auth_header.split()
            if len(parts) != 2 or parts[0] != self.keyword:
                return None

            token = parts[1]
        except (ValueError, IndexError):
            return None

        # Ищем токен в базе данных
        try:
            # Хешируем токен для поиска
            token_hash = ClientAPIToken.hash_token(token)
            api_token = ClientAPIToken.objects.select_related('user').get(
                token=token_hash,
                is_active=True
            )
        except ClientAPIToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        # Проверяем валидность токена
        if not api_token.is_valid():
            raise exceptions.AuthenticationFailed('Token is expired or inactive.')

        # Отмечаем использование токена
        api_token.mark_used()

        return (api_token.user, api_token)

