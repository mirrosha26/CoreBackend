from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import Throttled
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# Импортируем модель для счетчиков бесплатных пользователей
try:
    from .models import FreeUserRequestCounter
except ImportError:
    FreeUserRequestCounter = None


class DailyRateThrottle(UserRateThrottle):
    """
    Throttling класс для ограничения количества запросов.
    
    Логика применения лимита:
    - Если у пользователя есть группа - лимит применяется на группу (общий для всех участников)
      - Флаг is_paid берется из группы
    - Если группы нет - лимит применяется на пользователя (личный лимит)
      - Флаг is_paid берется из пользователя
    
    Типы лимитов:
    - Бесплатный (is_paid=False): FREE_CLIENT_LIMIT токенов всего (общее количество, не дневное)
    - Оплаченный (is_paid=True): CLIENT_API_DAILY_RATE_LIMIT токенов в день
    
    Использует кеш для отслеживания количества запросов.
    """
    # Лимит запросов в сутки (можно настроить через settings)
    scope = 'daily'
    # Формат ключа кеша (из базового класса UserRateThrottle)
    cache_format = 'throttle_%(scope)s_%(ident)s'
    
    def get_is_paid(self, request):
        """
        Определяет, является ли доступ оплаченным.
        Если есть группа - берем флаг из группы, иначе из пользователя.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Если у пользователя есть группа, используем флаг группы
        if hasattr(request.user, 'group') and request.user.group:
            return getattr(request.user.group, 'is_paid', False)
        
        # Если группы нет, используем флаг пользователя
        return getattr(request.user, 'is_paid', False)
    
    def get_rate(self, request=None):
        """
        Получает лимит запросов из настроек в зависимости от типа доступа.
        Для оплаченных - дневной лимит, для бесплатных - общий лимит.
        
        Если request не передан, возвращает дефолтный лимит (для совместимости с базовым классом).
        """
        from django.conf import settings
        
        # Если request не передан, возвращаем дефолтный лимит
        if request is None:
            daily_limit = getattr(settings, 'CLIENT_API_DAILY_RATE_LIMIT', 500)
            return f'{daily_limit}/day'
        
        is_paid = self.get_is_paid(request)
        
        if is_paid:
            # Оплаченный доступ: дневной лимит
            daily_limit = getattr(settings, 'CLIENT_API_DAILY_RATE_LIMIT', 500)
            return f'{daily_limit}/day'
        else:
            # Бесплатный доступ: общий лимит (используем формат /day, но не фильтруем по дате)
            free_limit = getattr(settings, 'FREE_CLIENT_LIMIT', 100)
            return f'{free_limit}/day'  # Используем /day для совместимости с parse_rate
    
    def get_cache_key(self, request, view):
        """
        Генерирует ключ кеша для отслеживания запросов.
        Если у пользователя есть группа - используем группу (общий лимит для всех участников).
        Если группы нет - используем пользователя (личный лимит).
        
        Для оплаченных: ключ с датой (дневной лимит)
        Для бесплатных: ключ без даты (общий лимит)
        """
        if request.user and request.user.is_authenticated:
            is_paid = self.get_is_paid(request)
            
            # Если у пользователя есть группа, используем группу для общего лимита
            if hasattr(request.user, 'group') and request.user.group:
                ident = f'group_{request.user.group.id}'
            else:
                # Если группы нет, используем личный лимит пользователя
                ident = f'user_{request.user.id}'
            
            if is_paid:
                # Оплаченный доступ: добавляем дату для дневного лимита
                today = timezone.now().date()
                ident = f'{ident}_{today}'
            # Для бесплатных не добавляем дату - общий лимит
            
            return self.cache_format % {
                'scope': self.scope,
                'ident': ident
            }
        return None
    
    def allow_request(self, request, view):
        """
        Проверяет, разрешен ли запрос на основе лимита.
        """
        if request.user and request.user.is_authenticated:
            # Получаем лимит (зависит от типа доступа)
            rate_str = self.get_rate(request)
            num_requests, duration = self.parse_rate(rate_str)
            
            # Генерируем ключ кеша
            key = self.get_cache_key(request, view)
            if key is None:
                return True
            
            # Получаем текущее количество запросов
            history = cache.get(key, [])
            now = timezone.now()
            
            is_paid = self.get_is_paid(request)
            
            if is_paid:
                # Оплаченный доступ: фильтруем запросы за последние 24 часа
                cutoff = now - timedelta(days=1)
                history = [h for h in history if h > cutoff]
                cache_timeout = 25 * 60 * 60  # 25 часов для дневного лимита
            else:
                # Бесплатный доступ: используем БД для персистентного хранения
                if FreeUserRequestCounter is not None:
                    try:
                        with transaction.atomic():
                            # Определяем, для кого считать (группа или пользователь)
                            if hasattr(request.user, 'group') and request.user.group:
                                counter = FreeUserRequestCounter.objects.select_for_update().get_or_create(
                                    group=request.user.group,
                                    defaults={'request_count': 0}
                                )[0]
                            else:
                                counter = FreeUserRequestCounter.objects.select_for_update().get_or_create(
                                    user=request.user,
                                    defaults={'request_count': 0}
                                )[0]
                            
                            # Проверяем лимит из БД
                            if counter.request_count >= num_requests:
                                # Лимит превышен
                                self.num_requests = num_requests
                                self.is_paid = is_paid
                                return False
                            
                            # Увеличиваем счетчик в БД атомарно
                            counter.request_count += 1
                            counter.save(update_fields=['request_count', 'updated_at'])
                            
                            # Не сохраняем в кеш для бесплатных - используем только БД
                            # Кеш используется только как fallback при ошибке БД
                            
                            return True
                    except Exception as e:
                        logger.error(f"Error accessing FreeUserRequestCounter: {e}")
                        # Fallback на кеш при ошибке БД
                        # Проверяем тип данных в кеше - может быть старый формат (целое число)
                        if isinstance(history, int):
                            # Старый формат: используем целое число как счетчик запросов
                            # Проверяем лимит напрямую
                            if history >= num_requests:
                                self.num_requests = num_requests
                                self.is_paid = is_paid
                                return False
                            # Увеличиваем счетчик и сохраняем обратно в кеш
                            cache.set(key, history + 1, 365 * 24 * 60 * 60)
                            return True
                        elif not isinstance(history, list):
                            # Если это не список и не целое число, инициализируем пустым списком
                            history = []
                        cache_timeout = 365 * 24 * 60 * 60
                else:
                    # Если модель недоступна, используем кеш (старое поведение)
                    # Проверяем тип данных в кеше - может быть старый формат (целое число)
                    if isinstance(history, int):
                        # Старый формат: используем целое число как счетчик запросов
                        # Проверяем лимит напрямую
                        if history >= num_requests:
                            self.num_requests = num_requests
                            self.is_paid = is_paid
                            return False
                        # Увеличиваем счетчик и сохраняем обратно в кеш
                        cache.set(key, history + 1, 365 * 24 * 60 * 60)
                        return True
                    elif not isinstance(history, list):
                        # Если это не список и не целое число, инициализируем пустым списком
                        history = []
                    cache_timeout = 365 * 24 * 60 * 60
            
            # Для оплаченных или fallback для бесплатных (со списком): проверяем лимит в кеше
            # history должен быть списком на этом этапе
            if not isinstance(history, list):
                history = []
            if len(history) >= num_requests:
                # Лимит превышен - сохраняем информацию для сообщения об ошибке
                self.num_requests = num_requests
                self.is_paid = is_paid
                return False
            
            # Добавляем текущий запрос
            history.append(now)
            # Сохраняем в кеш
            cache.set(key, history, cache_timeout)
            
            return True
        
        # Если пользователь не аутентифицирован, разрешаем (аутентификация уже проверена)
        return True
    
    def wait(self):
        """
        Возвращает время ожидания до следующего разрешенного запроса.
        В случае суточного лимита возвращаем время до начала следующего дня.
        """
        now = timezone.now()
        # Время до начала следующего дня
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()
        return wait_seconds
    
    def throttle_failure(self):
        """
        Вызывается когда лимит превышен. Выбрасывает кастомное исключение Throttled.
        """
        num_requests = getattr(self, 'num_requests', 1000)
        is_paid = getattr(self, 'is_paid', True)
        
        if is_paid:
            # Оплаченный доступ: дневной лимит
            wait_time = self.wait()
            message = f'Daily request limit exceeded. Limit: {num_requests} requests per day.'
            wait_seconds = int(wait_time)
        else:
            # Бесплатный доступ: общий лимит
            message = f'Total request limit exceeded. Limit: {num_requests} requests total.'
            wait_seconds = None  # Для бесплатных нет времени ожидания
        
        # Формируем ответ в стандартном формате Client API
        error_response = {
            'error': 'throttled',
            'message': message,
            'details': {
                'limit': num_requests,
            }
        }
        
        # Добавляем wait_seconds только для оплаченных (если есть)
        if wait_seconds is not None:
            error_response['details']['wait_seconds'] = wait_seconds
        
        raise Throttled(detail=error_response)

