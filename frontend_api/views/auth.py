from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from ..serializers.auth import PasswordResetRequestSerializer, PasswordResetResponseSerializer
from ..utils.mailgun_sender import mailgun_sender

from profile.models import User, USER_TYPES
from ..serializers import UserSerializer


class BaseAuthView(APIView):
    """Base class for authentication views"""
    
    def validate_email_field(self, email):
        """Email validation"""
        if not email:
            return False, {
                'success': False,
                'error_code': 'MISSING_EMAIL',
                'message': 'Email is required.'
            }
        
        try:
            validate_email(email)
            return True, None
        except ValidationError as e:
            return False, {
                'success': False,
                'error_code': 'INVALID_EMAIL',
                'message': e.message if hasattr(e, 'message') else e.messages[0]
            }
    
    def create_token_response(self, user, first_login=False, message='Operation successful'):
        """Creates standard response with tokens"""
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)
        
    def error_response(self, error_code, message, status_code):
        """Creates standard error response"""
        return Response({
            'success': False,
            'error_code': error_code,
            'message': message
        }, status=status_code)

class LoginView(BaseAuthView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            
            email = data.get('email', '').strip().lower()
            password = data.get('password', '').strip()

            if not password:
                return self.error_response(
                    'MISSING_FIELDS',
                    'Please fill in all required fields.',
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Email validation
            is_valid, error_response = self.validate_email_field(email)
            if not is_valid:
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Find user by email
                user = User.objects.get(email=email)
                
                # Проверяем активность пользователя до аутентификации
                if not user.is_active:
                    return self.error_response(
                        'USER_INACTIVE',
                        'Account is not activated. Please contact veck team.',
                        status.HTTP_403_FORBIDDEN
                    )

                # User authentication
                authenticated_user = authenticate(username=user.username, password=password)
                
                if not authenticated_user:
                    return self.error_response(
                        'INVALID_CREDENTIALS',
                        'Invalid password.',
                        status.HTTP_401_UNAUTHORIZED
                    )

                # Check first login
                first_login = authenticated_user.last_login is None
                
                # Update last login info
                authenticated_user.save(update_fields=['last_login'])
                
                return self.create_token_response(authenticated_user, first_login, 'Login successful.')

            except User.DoesNotExist:
                return self.error_response(
                    'USER_NOT_FOUND',
                    'User with this email not found.',
                    status.HTTP_404_NOT_FOUND
                )
            except Exception:
                return self.error_response(
                    'DATABASE_ERROR',
                    'An error occurred while searching for user. Please try again later.',
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception:
            return self.error_response(
                'SERVER_ERROR',
                'An error occurred while processing the request. Please try again later.',
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            data = request.data
            
            # Get email and password
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()
            
            if not email or not password:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_FIELDS', 
                    'message': 'Please provide email and password.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Generate username from email
            email_parts = email.split('@')
            if len(email_parts) != 2:
                return Response({
                    'success': False,
                    'error_code': 'INVALID_EMAIL',
                    'message': 'Please provide a valid email address.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            domain = email_parts[1].replace('.', '-')
            username = f"{email_parts[0]}@{domain}"
            
            # Check username uniqueness
            if User.objects.filter(username=username).exists():
                return Response({
                    'success': False,
                    'error_code': 'USERNAME_EXISTS',
                    'message': 'User with this email already exists.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_active=False,
                user_type=data.get('user_type', USER_TYPES[0][0] if USER_TYPES else None),
                first_name=data.get('first_name', '')
            )
            
            return Response({
                "success": True,
                "message": "Registration completed successfully. Please wait for account activation."
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': 'An error occurred while processing the request. Please try again later.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegistrationMetaView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            # Use USER_TYPES directly from module
            user_types = [
                {'value': key, 'label': label} 
                for key, label in USER_TYPES
            ]
            
            return Response({
                'success': True,
                'data': {
                    'user_types': user_types
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': 'An error occurred while retrieving registration data.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Простой эндпоинт для сброса пароля
    Получает email, проверяет существование пользователя и отправляет письмо
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'Invalid email format',
            'error': 'Please provide a valid email address'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    try:
        # Проверяем, существует ли пользователь с таким email
        user = User.objects.get(email=email)
        
        # Отправляем email через Mailgun
        reset_url = f"https://theveck.com/reset-password/test-token-123"  # Пока тестовая ссылка
        
        email_sent = mailgun_sender.send_password_reset_email(user, reset_url)
        
        if not email_sent:
            return Response({
                'success': False,
                'message': 'Failed to send password reset email',
                'error': 'Email service temporarily unavailable'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': True,
            'message': f'Password reset email sent to {email}',
            'error': ''
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        # Не раскрываем, что пользователь не существует (безопасность)
        return Response({
            'success': True,
            'message': f'If an account with email {email} exists, a password reset email has been sent',
            'error': ''
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Failed to process password reset request',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# Client API Token Management Views
# ============================================================================

class ClientAPITokenListView(APIView):
    """
    Получение списка Client API токенов пользователя.
    GET /auth/client-tokens/ - список всех активных Client API токенов
    """
    permission_classes = [IsAuthenticated]
    
    def get_access_info(self, user):
        """
        Получает информацию о типе доступа и оставшихся запросах для Client API.
        """
        # Импортируем здесь, чтобы избежать циклических импортов
        try:
            from client_api.models import FreeUserRequestCounter
        except ImportError:
            FreeUserRequestCounter = None
        
        # Определяем тип доступа (платный/бесплатный) - только для Client API
        if hasattr(user, 'group') and user.group:
            is_paid = getattr(user.group, 'is_paid', False)
            ident_for_cache = f'group_{user.group.id}'
        else:
            is_paid = getattr(user, 'is_paid', False)
            ident_for_cache = f'user_{user.id}'
        
        # Получаем лимиты из settings (только для Client API)
        if is_paid:
            limit = getattr(settings, 'CLIENT_API_DAILY_RATE_LIMIT', 500)
        else:
            limit = getattr(settings, 'FREE_CLIENT_LIMIT', 100)
        
        # Получаем текущий счетчик запросов (только для Client API)
        current_count = 0
        
        if is_paid:
            # Оплаченный доступ: получаем из кеша (дневной лимит)
            today = timezone.now().date()
            cache_key = f'throttle_daily_{ident_for_cache}_{today}'
            history = cache.get(cache_key, [])
            now = timezone.now()
            cutoff = now - timedelta(days=1)
            # Фильтруем запросы за последние 24 часа
            current_count = len([h for h in history if h > cutoff])
        else:
            # Бесплатный доступ: получаем из БД (общий лимит)
            if FreeUserRequestCounter is not None:
                try:
                    if hasattr(user, 'group') and user.group:
                        counter = FreeUserRequestCounter.objects.filter(group=user.group).first()
                    else:
                        counter = FreeUserRequestCounter.objects.filter(user=user).first()
                    
                    if counter:
                        current_count = counter.request_count
                except Exception:
                    pass  # Если ошибка, используем 0
        
        # Вычисляем оставшиеся запросы
        remaining = max(0, limit - current_count)
        
        return {
            'is_paid': is_paid,
            'access_type': 'paid' if is_paid else 'free',
            'limit': limit,
            'current_count': current_count,
            'remaining': remaining
        }
    
    def get(self, request):
        """
        Возвращает список всех активных Client API токенов пользователя с информацией о доступе.
        """
        try:
            from client_api.models import ClientAPIToken
            from django.core.exceptions import ValidationError
            
            user = request.user
            
            # Получаем информацию о доступе
            access_info = self.get_access_info(user)
            
            # Получаем все активные токены пользователя
            client_tokens = ClientAPIToken.objects.filter(
                user=user,
                is_active=True
            ).order_by('-created_at')
            
            # Формируем данные токенов
            tokens_data = []
            for token in client_tokens:
                tokens_data.append({
                    'id': token.id,
                    'name': token.name,
                    'token_prefix': token.token_prefix,
                    'created_at': token.created_at.isoformat() if token.created_at else None,
                    'last_used_at': token.last_used_at.isoformat() if token.last_used_at else None,
                    'is_active': token.is_active,
                })
            
            # Количество токенов, которые можно создать (максимум 5)
            active_tokens_count = len(tokens_data)
            max_tokens = 5
            tokens_available = max(0, max_tokens - active_tokens_count)
            
            # Определяем, является ли доступ групповым
            is_group_access = hasattr(user, 'group') and user.group is not None
            group_info = None
            if is_group_access:
                group_info = {
                    'id': user.group.id,
                    'name': user.group.name,
                    'slug': user.group.slug,
                }
            
            return Response({
                'success': True,
                'data': {
                    'tokens': tokens_data,
                    'tokens_count': active_tokens_count,
                    'tokens_available': tokens_available,
                    'max_tokens': max_tokens,
                },
                'access': {
                    'type': access_info['access_type'],
                    'is_paid': access_info['is_paid'],
                    'limit': access_info['limit'],
                    'current_count': access_info['current_count'],
                    'remaining': access_info['remaining'],
                    'is_group_access': is_group_access,  # Флаг группового доступа
                    'group': group_info,  # Информация о группе (если есть)
                    'note': ('Request limit is shared across all group members.' if is_group_access else None)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while retrieving tokens: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientAPITokenCreateView(APIView):
    """
    Создание нового Client API токена для пользователя.
    POST /auth/client-tokens/create/ - создание нового Client API токена
    
    Примечание: Максимум 5 активных токенов на пользователя.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Создает новый Client API токен для текущего пользователя.
        
        Параметры:
        - name (обязательно): название токена для идентификации
        """
        try:
            from client_api.models import ClientAPIToken
            from django.core.exceptions import ValidationError
            
            user = request.user
            
            # Получаем имя токена из запроса (обязательно)
            token_name = request.data.get('name', '').strip()
            if not token_name:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_NAME',
                    'message': 'Token name is required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Генерируем новый токен
            full_token, token_hash, token_prefix = ClientAPIToken.generate_token()
            
            # Создаем токен (валидация на максимум 5 токенов происходит в clean())
            try:
                client_token = ClientAPIToken.objects.create(
                    user=user,
                    name=token_name,
                    token=token_hash,
                    token_prefix=token_prefix,
                    is_active=True
                )
            except ValidationError as e:
                return Response({
                    'success': False,
                    'error_code': 'TOKEN_LIMIT_EXCEEDED',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Возвращаем полный токен только один раз (при создании)
            return Response({
                'success': True,
                'data': {
                    'id': client_token.id,
                    'name': client_token.name,
                    'token': full_token,  # Полный токен возвращается только при создании
                    'token_prefix': client_token.token_prefix,
                    'created_at': client_token.created_at.isoformat() if client_token.created_at else None,
                    'is_active': client_token.is_active,
                    'warning': 'Save this token now. You will not be able to see it again.'
                },
                'message': 'Token created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while creating token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientAPITokenDeleteView(APIView):
    """
    Удаление Client API токена.
    DELETE /auth/client-tokens/<token_id>/delete/ - удаление токена по ID
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, token_id=None):
        """
        Полностью удаляет Client API токен из базы данных.
        После удаления токен больше нельзя использовать для аутентификации.
        """
        try:
            from client_api.models import ClientAPIToken
            
            user = request.user
            
            # Если token_id не передан в URL, пытаемся получить из body
            if not token_id:
                token_id = request.data.get('token_id') or request.data.get('id')
            
            if not token_id:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_TOKEN_ID',
                    'message': 'Token ID is required. Provide it in URL path or request body.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Находим токен пользователя
            try:
                client_token = ClientAPIToken.objects.get(
                    id=token_id,
                    user=user
                )
            except ClientAPIToken.DoesNotExist:
                return Response({
                    'success': False,
                    'error_code': 'TOKEN_NOT_FOUND',
                    'message': 'Token not found or does not belong to current user.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Полностью удаляем токен из БД
            client_token.delete()
            
            return Response({
                'success': True,
                'message': 'Token has been successfully deleted.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while deleting token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)