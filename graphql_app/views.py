from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from strawberry.django.views import GraphQLView

from .schema import schema

User = get_user_model()


class JWTCookieAuthentication(JWTAuthentication):
    """JWT аутентификация, читающая токены из cookies."""
    
    def authenticate(self, request):
        raw_token = request.COOKIES.get('accessToken')
        
        if raw_token is None:
            return super().authenticate(request)
        
        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        
        return (user, validated_token)
    
    def get_validated_token(self, raw_token):
        """Валидирует JWT токен и возвращает валидированный объект токена."""
        messages = []
        for AuthToken in api_settings.AUTH_TOKEN_CLASSES:
            try:
                return AuthToken(raw_token)
            except TokenError as e:
                messages.append({
                    'token_class': AuthToken.__name__,
                    'token_type': AuthToken.token_type,
                    'message': e.args[0]
                })

        raise InvalidToken({
            'detail': _('Given token not valid for any token type'),
            'messages': messages,
        })


class CSRFExemptSessionAuthentication(SessionAuthentication):
    """Сессионная аутентификация без проверки CSRF для GraphQL эндпоинтов."""
    
    def enforce_csrf(self, request):
        pass


@method_decorator(csrf_exempt, name='dispatch')
class AuthenticatedGraphQLView(GraphQLView):
    """GraphQL view с поддержкой JWT cookie, Bearer токена и сессионной аутентификации."""
    
    def __init__(self, **kwargs):
        super().__init__(schema=schema, **kwargs)
    
    def dispatch(self, request, *args, **kwargs):
        self.authenticate_request(request)
        return super().dispatch(request, *args, **kwargs)
    
    def authenticate_request(self, request):
        """Применяет аутентификацию DRF к запросу."""
        drf_request = Request(request)
        
        authenticators = [
            JWTCookieAuthentication(),
            JWTAuthentication(),
            TokenAuthentication(),
            CSRFExemptSessionAuthentication(),
        ]
        
        for authenticator in authenticators:
            try:
                user_auth = authenticator.authenticate(drf_request)
                if user_auth:
                    user, auth = user_auth
                    request.user = user
                    request.auth = auth
                    break
            except Exception:
                continue 