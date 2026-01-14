from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound, Throttled
from rest_framework.renderers import JSONRenderer
from django.db.models import Prefetch, Count, Max, Min, Q, Exists, OuterRef
from django.db.models.functions import Lower
from datetime import datetime, time
from django.utils import timezone
from collections import defaultdict
import logging

from signals.models import SignalCard, Signal, Participant, PARTICIPANTS_TYPES, Category, STAGES, ROUNDS
from client_api.serializers.cards import serialize_card_previews, serialize_card_detail, serialize_interactions
from client_api.serializers.participants import serialize_participant, serialize_participants
from profile.models import SavedParticipant, UserFolder, FolderCard, SavedFilter
from signals.utils import apply_search_query_filters

from .authentication import ClientAPITokenAuthentication
from .throttling import DailyRateThrottle

logger = logging.getLogger(__name__)


class ClientAPIView(APIView):
    """
    Base view class for Client API with consistent error handling.
    All errors are returned in JSON format.
    """
    authentication_classes = [ClientAPITokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [DailyRateThrottle]
    
    def check_throttles(self, request):
        """
        Переопределяем для кастомной обработки throttling с нашим форматом ошибки.
        """
        for throttle in self.get_throttles():
            if not throttle.allow_request(request, self):
                # Если лимит превышен, вызываем кастомный метод для создания исключения
                if hasattr(throttle, 'throttle_failure'):
                    throttle.throttle_failure()
                else:
                    # Стандартная обработка DRF
                    wait_time = throttle.wait()
                    raise Throttled(wait_time)
    
    def handle_exception(self, exc):
        """
        Override to ensure all exceptions return JSON responses.
        """
        from .exceptions import client_api_exception_handler
        response = client_api_exception_handler(exc, self.get_view_context())
        if response is None:
            response = super().handle_exception(exc)
        return response
    
    def get_view_context(self):
        """
        Get context for exception handler.
        """
        return {
            'view': self,
            'args': getattr(self, 'args', ()),
            'kwargs': getattr(self, 'kwargs', {}),
            'request': getattr(self, 'request', None)
        }
    
    def get_object_or_404_json(self, queryset, **filters):
        """
        Get object or return 404 in JSON format.
        
        Args:
            queryset: Django queryset
            **filters: Filter arguments
            
        Returns:
            Model instance
            
        Raises:
            NotFound: If object not found (returns JSON 404)
        """
        try:
            return queryset.get(**filters)
        except queryset.model.DoesNotExist:
            raise NotFound('Resource not found')


class APIVersionsView(APIView):
    """
    View для получения списка доступных версий API.
    Доступен без аутентификации.
    Всегда возвращает JSON (не HTML).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    renderer_classes = [JSONRenderer]  # Гарантируем JSON ответ
    
    def get(self, request):
        """
        Возвращает список доступных версий API.
        """
        return Response({
            'versions': [
                {
                    'version': 'v1',
                    'status': 'current',
                    'base_url': '/client_api/v1/',
                    'endpoints': {
                        'token': '/client_api/v1/token/validate/',
                        'cards': '/client_api/v1/cards/',
                        'participants': '/client_api/v1/participants/',
                    }
                }
            ],
            'current_version': 'v1'
        }, status=status.HTTP_200_OK)


class TokenValidationView(ClientAPIView):
    """
    Эндпоинт для проверки валидности токена.
    GET /api/client-api/token/validate/ - проверка токена
    """
    permission_classes = [AllowAny]  # Разрешаем доступ без аутентификации для проверки

    def get(self, request):
        """Проверяет валидность токена из заголовка Authorization"""
        if request.user.is_authenticated:
            # Токен валиден
            return Response({
                'valid': True,
                'message': 'Token is valid',
                'user': {
                    'username': request.user.username,
                    'email': request.user.email,
                }
            }, status=status.HTTP_200_OK)
        else:
            # Токен невалиден или отсутствует
            return Response({
                'valid': False,
                'message': 'Invalid or missing token'
            }, status=status.HTTP_401_UNAUTHORIZED)


class CardListView(ClientAPIView):
    """
    Эндпоинт для получения всех сигнальных карт.
    GET /v1/cards/ - получение списка карт
    
    Параметры запроса:
    - limit: количество записей (по умолчанию 20, максимум 100)
    - offset: смещение (по умолчанию 0)
    - sort: preset или custom сортировка (по умолчанию 'latest_signal_date:desc' - как в GraphQL)
    - include_user_data: если true, добавляет пользовательские данные (is_liked, has_note, note, folders)
    
    Preset сортировки:
    - trending: interactions_count:desc,latest_signal_date:desc
    - recent: created_at:desc
    - most_active: updated_at:desc,interactions_count:desc
    
    Custom сортировка:
    Формат: field:direction,field:direction
    Разрешенные поля: created_at, updated_at, name (+), interactions_count, latest_signal_date
    Направления: asc, desc
    
    Примеры:
    - GET /v1/cards/?sort=trending
    - GET /v1/cards/?sort=recent
    - GET /v1/cards/?sort=interactions_count:desc,latest_signal_date:desc
    """
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Проверяем, указан ли filter_id для применения сохраненного фильтра
        filter_id_param = request.query_params.get('filter_id')
        saved_filter = None
        if filter_id_param:
            try:
                filter_id = int(filter_id_param)
                saved_filter = SavedFilter.objects.filter(user=user, id=filter_id).prefetch_related('categories', 'participants').first()
                if not saved_filter:
                    return Response({
                        'error': 'not_found',
                        'message': f'Filter with id {filter_id} not found or does not belong to user'
                    }, status=status.HTTP_404_NOT_FOUND)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидный filter_id
        
        # Получаем все открытые карточки с предзагрузкой связанных данных
        # is_open - внутренний атрибут, всегда True, игнорируем его в фильтрах
        signal_cards = (SignalCard.objects
            .filter(is_open=True)
            .prefetch_related(
                'categories',
                'categories__parent_category',
                Prefetch(
                    'signals',
                    queryset=Signal.objects.select_related(
                        'participant',
                        'associated_participant'
                    )
                )
            )
        )
        
        # Сортировка
        # По умолчанию используем latest_signal_date (как в GraphQL), а не recent
        sort_param = request.query_params.get('sort', 'latest_signal_date:desc')
        
        # Preset сортировки
        sort_presets = {
            'trending': ['interactions_count:desc', 'latest_signal_date:desc'],
            'recent': ['created_at:desc'],
            'most_active': ['updated_at:desc', 'interactions_count:desc']
        }
        
        # Разрешенные поля для сортировки
        allowed_sort_fields = ['created_at', 'updated_at', 'name', 'interactions_count', 'latest_signal_date']
        
        # Всегда добавляем interactions_count для отображения в списке
        signal_cards = signal_cards.annotate(interactions_count=Count('signals', distinct=True))
        
        # Парсим параметр сортировки
        if sort_param in sort_presets:
            # Preset сортировка
            sort_fields = sort_presets[sort_param]
        else:
            # Custom сортировка: парсим формат "field:direction,field:direction"
            sort_fields = [s.strip() for s in sort_param.split(',')]
        
        # Проверяем, какие аннотации нужны
        needs_name_lower = False
        for sort_field in sort_fields:
            field_name = sort_field.split(':')[0]
            if field_name == 'name':
                needs_name_lower = True  # Для case-insensitive сортировки
        
        # Всегда добавляем latest_signal_date для отображения last_interaction_at
        signal_cards = signal_cards.annotate(latest_signal_date=Max('signals__created_at'))
        # Добавляем oldest_signal_date для отображения first_interaction_at
        signal_cards = signal_cards.annotate(oldest_signal_date=Min('signals__created_at'))
        
        # Добавляем остальные необходимые аннотации
        if needs_name_lower:
            signal_cards = signal_cards.annotate(name_lower=Lower('name'))
        
        # Применяем фильтры из saved_filter, если он указан
        # Фильтры из query_params будут иметь приоритет и переопределят фильтры из saved_filter
        if saved_filter:
            # Категории - применяем только если не указаны в query_params
            # Используем ту же логику, что и в GraphQL: Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
            categories_param = request.query_params.get('categories')
            if not categories_param and saved_filter.categories.exists():
                category_ids = [cat.id for cat in saved_filter.categories.all()]
                # Используем ту же логику, что и в GraphQL
                category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
                signal_cards = signal_cards.filter(category_filter).distinct()
            
            # Стадии и раунды (ИЛИ между собой) - применяем только если не указаны в query_params
            stages_param = request.query_params.get('stages')
            rounds_param = request.query_params.get('rounds')
            if not stages_param and not rounds_param and (saved_filter.stages or saved_filter.round_statuses):
                stage_q = Q()
                round_q = Q()
                
                if saved_filter.stages:
                    # stages в SavedFilter хранятся как список строк
                    valid_stages = [stage for stage in saved_filter.stages if stage in dict(STAGES)]
                    if valid_stages:
                        stage_q = Q(stage__in=valid_stages)
                
                if saved_filter.round_statuses:
                    # round_statuses в SavedFilter хранятся как список строк
                    valid_rounds = [round_status for round_status in saved_filter.round_statuses if round_status in dict(ROUNDS)]
                    if valid_rounds:
                        round_q = Q(round_status__in=valid_rounds)
                
                if stage_q and round_q:
                    signal_cards = signal_cards.filter(stage_q | round_q)
                elif stage_q:
                    signal_cards = signal_cards.filter(stage_q)
                elif round_q:
                    signal_cards = signal_cards.filter(round_q)
            
            # Локации - убрано, поля location удалены из модели SignalCard
            
            # Участники - применяем только если не указаны в query_params
            # Поддерживаем как legacy (participants), так и advanced (participant_filter_mode) фильтрацию
            participants_param = request.query_params.get('participants')
            if not participants_param:
                # Advanced participant filtering (как в GraphQL)
                if saved_filter.participant_filter_mode:
                    participant_filter_ids = saved_filter.participant_filter_ids or []
                    participant_filter_types = saved_filter.participant_filter_types or []
                    
                    # Collect legacy participant IDs to include alongside advanced filtering
                    legacy_participant_ids = []
                    if saved_filter.participants.exists():
                        legacy_participant_ids = [p.id for p in saved_filter.participants.all()]
                    
                    if saved_filter.participant_filter_mode == 'INCLUDE_ONLY':
                        # Only show signals from these specific participants (combine both sources)
                        all_included_ids = participant_filter_ids + legacy_participant_ids
                        if all_included_ids:
                            participant_signals = Signal.objects.filter(
                                Q(participant_id__in=all_included_ids) | 
                                Q(associated_participant_id__in=all_included_ids),
                                signal_card=OuterRef('pk')
                            )
                            signal_cards = signal_cards.filter(Exists(participant_signals))
                    elif saved_filter.participant_filter_mode == 'EXCLUDE_FROM_TYPE':
                        # Include participants of specified types, exclude specific IDs, plus legacy participants
                        if participant_filter_types:
                            filter_conditions = Q()
                            
                            # 1. Include signals from participants of specified types, excluding specific IDs
                            type_filter = Q(
                                Q(participant__type__in=participant_filter_types) | 
                                Q(associated_participant__type__in=participant_filter_types)
                            )
                            
                            # Exclude specific participant IDs from the type selection if provided
                            if participant_filter_ids:
                                type_filter &= ~(
                                    Q(participant_id__in=participant_filter_ids) | 
                                    Q(associated_participant_id__in=participant_filter_ids)
                                )
                            
                            filter_conditions |= type_filter
                            
                            # 2. Additionally include signals from legacy participants (regardless of type)
                            if legacy_participant_ids:
                                legacy_filter = Q(
                                    Q(participant_id__in=legacy_participant_ids) | 
                                    Q(associated_participant_id__in=legacy_participant_ids)
                                )
                                filter_conditions |= legacy_filter
                            
                            # Apply the combined filter
                            participant_signals = Signal.objects.filter(
                                filter_conditions,
                                signal_card=OuterRef('pk')
                            )
                            signal_cards = signal_cards.filter(Exists(participant_signals))
                        elif legacy_participant_ids:
                            # No participant types specified, just use legacy participants
                            participant_signals = Signal.objects.filter(
                                Q(participant_id__in=legacy_participant_ids) | 
                                Q(associated_participant_id__in=legacy_participant_ids),
                                signal_card=OuterRef('pk')
                            )
                            signal_cards = signal_cards.filter(Exists(participant_signals))
                elif saved_filter.participants.exists():
                    # Legacy participant filtering only (when no advanced filtering is set)
                    participant_ids = [p.id for p in saved_filter.participants.all()]
                    participant_signals = Signal.objects.filter(
                        Q(participant_id__in=participant_ids) | 
                        Q(associated_participant_id__in=participant_ids),
                        signal_card=OuterRef('pk')
                    )
                    signal_cards = signal_cards.filter(Exists(participant_signals))
            
            # Даты - применяем только если не указаны в query_params
            created_after = request.query_params.get('created_after')
            created_before = request.query_params.get('created_before')
            if not created_after and saved_filter.start_date:
                start_datetime = timezone.make_aware(datetime.combine(saved_filter.start_date, time.min))
                signal_cards = signal_cards.filter(created_at__gte=start_datetime)
            if not created_before and saved_filter.end_date:
                end_datetime = timezone.make_aware(datetime.combine(saved_filter.end_date, time.max))
                signal_cards = signal_cards.filter(created_at__lte=end_datetime)
            
            # Display preference (web3/web2/all) - убрано из saved_filter, используем только из query_params
            
            # Search - применяем только если не указан в query_params
            search_param = request.query_params.get('search')
            if not search_param and saved_filter.search:
                signal_cards, _ = apply_search_query_filters(signal_cards, saved_filter.search)
            
            # Featured - применяем только если не указан в query_params
            featured_param = request.query_params.get('featured')
            if featured_param is None and saved_filter.featured is not None:
                signal_cards = signal_cards.filter(featured=saved_filter.featured)
            
            # is_open - игнорируем, это внутренний атрибут, всегда True
            
            # New - карточки, созданные за последние 7 дней
            # new=true → только новые карточки (последние 7 дней)
            # new=false → фильтр не применяется (показываются все карточки)
            new_param = request.query_params.get('new')
            if new_param is None and saved_filter.new is not None and saved_filter.new:
                from datetime import timedelta
                seven_days_ago = timezone.now() - timedelta(days=7)
                # Фильтр для новых карточек (созданных за последние 7 дней)
                signal_cards = signal_cards.filter(created_at__gte=seven_days_ago)
            
            # Trending - проекты с минимум 5 уникальными участниками за последнюю неделю
            # Упрощенная версия: используем interactions_count (уже аннотировано)
            trending_param = request.query_params.get('trending')
            if trending_param is None and saved_filter.trending is not None:
                # Для trending используем упрощенную логику: карточки с interactions_count >= 5
                # и latest_signal_date в пределах последней недели
                if saved_filter.trending:
                    from datetime import timedelta
                    one_week_ago = timezone.now() - timedelta(days=7)
                    signal_cards = signal_cards.filter(
                        interactions_count__gte=5,
                        latest_signal_date__gte=one_week_ago
                    )
                else:
                    # Не trending: либо interactions_count < 5, либо latest_signal_date старше недели
                    from datetime import timedelta
                    one_week_ago = timezone.now() - timedelta(days=7)
                    signal_cards = signal_cards.filter(
                        Q(interactions_count__lt=5) | Q(latest_signal_date__lt=one_week_ago) | Q(latest_signal_date__isnull=True)
                    )
            
            # Min/Max signals - фильтрация по количеству сигналов
            # Упрощенная версия: используем interactions_count (уже аннотировано)
            min_signals_param = request.query_params.get('min_signals')
            max_signals_param = request.query_params.get('max_signals')
            if min_signals_param is None and saved_filter.min_signals is not None:
                signal_cards = signal_cards.filter(interactions_count__gte=saved_filter.min_signals)
            if max_signals_param is None and saved_filter.max_signals is not None:
                signal_cards = signal_cards.filter(interactions_count__lte=saved_filter.max_signals)
        
        # Вспомогательная функция для парсинга даты
        def parse_date_filter(date_str, is_end_of_day=False):
            """Парсит дату в формате YYYY-MM-DD и возвращает datetime в UTC"""
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                if is_end_of_day:
                    return timezone.make_aware(datetime.combine(date_obj, time.max))
                else:
                    return timezone.make_aware(datetime.combine(date_obj, time.min))
            except (ValueError, AttributeError):
                return None
        
        # Фильтрация по дате создания карточки (created_at)
        created_after = request.query_params.get('created_after')
        created_before = request.query_params.get('created_before')
        if created_after:
            created_after_datetime = parse_date_filter(created_after, is_end_of_day=False)
            if created_after_datetime:
                signal_cards = signal_cards.filter(created_at__gte=created_after_datetime)
        if created_before:
            created_before_datetime = parse_date_filter(created_before, is_end_of_day=True)
            if created_before_datetime:
                signal_cards = signal_cards.filter(created_at__lte=created_before_datetime)
        
        # Фильтрация по дате обновления карточки (updated_at)
        updated_after = request.query_params.get('updated_after')
        updated_before = request.query_params.get('updated_before')
        if updated_after:
            updated_after_datetime = parse_date_filter(updated_after, is_end_of_day=False)
            if updated_after_datetime:
                signal_cards = signal_cards.filter(updated_at__gte=updated_after_datetime)
        if updated_before:
            updated_before_datetime = parse_date_filter(updated_before, is_end_of_day=True)
            if updated_before_datetime:
                signal_cards = signal_cards.filter(updated_at__lte=updated_before_datetime)
        
        # Фильтрация по дате последнего взаимодействия (last_interaction_at = latest_signal_date)
        # Аннотация latest_signal_date уже добавлена выше
        last_interaction_after = request.query_params.get('last_interaction_after')
        last_interaction_before = request.query_params.get('last_interaction_before')
        if last_interaction_after:
            last_interaction_after_datetime = parse_date_filter(last_interaction_after, is_end_of_day=False)
            if last_interaction_after_datetime:
                signal_cards = signal_cards.filter(latest_signal_date__gte=last_interaction_after_datetime)
        if last_interaction_before:
            last_interaction_before_datetime = parse_date_filter(last_interaction_before, is_end_of_day=True)
            if last_interaction_before_datetime:
                signal_cards = signal_cards.filter(latest_signal_date__lte=last_interaction_before_datetime)
        
        # Фильтрация по дате первого взаимодействия (first_interaction_at = oldest_signal_date)
        # Аннотация oldest_signal_date уже добавлена выше
        first_interaction_after = request.query_params.get('first_interaction_after')
        first_interaction_before = request.query_params.get('first_interaction_before')
        if first_interaction_after:
            first_interaction_after_datetime = parse_date_filter(first_interaction_after, is_end_of_day=False)
            if first_interaction_after_datetime:
                signal_cards = signal_cards.filter(oldest_signal_date__gte=first_interaction_after_datetime)
        if first_interaction_before:
            first_interaction_before_datetime = parse_date_filter(first_interaction_before, is_end_of_day=True)
            if first_interaction_before_datetime:
                signal_cards = signal_cards.filter(oldest_signal_date__lte=first_interaction_before_datetime)
        
        # Фильтрация по папкам (с проверкой принадлежности пользователю)
        folder_ids_param = request.query_params.get('folder_ids')
        if folder_ids_param:
            folder_ids = []
            for folder_id_str in folder_ids_param.split(','):
                try:
                    folder_id = int(folder_id_str.strip())
                    folder_ids.append(folder_id)
                except (ValueError, AttributeError):
                    continue
            
            # Убираем дубликаты
            folder_ids = list(set(folder_ids))
            
            if folder_ids:
                # Проверяем, что все папки принадлежат пользователю
                user_folders = UserFolder.objects.filter(user=user, id__in=folder_ids).values_list('id', flat=True)
                valid_folder_ids = list(user_folders)
                
                # Если указаны папки, но ни одна не валидна, возвращаем пустой результат
                if not valid_folder_ids:
                    signal_cards = signal_cards.none()
                else:
                    # Фильтруем карточки, которые есть хотя бы в одной из указанных папок
                    folder_cards = FolderCard.objects.filter(
                        folder_id__in=valid_folder_ids,
                        signal_card=OuterRef('pk')
                    )
                    signal_cards = signal_cards.filter(Exists(folder_cards))
        
        # Фильтрация по стадиям ИЛИ раундам (ИЛИ между группами, ИЛИ внутри каждой группы)
        stages_param = request.query_params.get('stages')
        rounds_param = request.query_params.get('rounds')
        
        if stages_param or rounds_param:
            stage_q = Q()
            round_q = Q()
            
            if stages_param:
                stage_slugs = [slug.strip() for slug in stages_param.split(',') if slug.strip()]
                valid_stages = [slug for slug in stage_slugs if slug in dict(STAGES)]
                if valid_stages:
                    stage_q = Q(stage__in=valid_stages)
            
            if rounds_param:
                round_slugs = [slug.strip() for slug in rounds_param.split(',') if slug.strip()]
                valid_rounds = [slug for slug in round_slugs if slug in dict(ROUNDS)]
                if valid_rounds:
                    round_q = Q(round_status__in=valid_rounds)
            
            # Применяем OR между стадиями и раундами
            if stage_q and round_q:
                signal_cards = signal_cards.filter(stage_q | round_q)
            elif stage_q:
                signal_cards = signal_cards.filter(stage_q)
            elif round_q:
                signal_cards = signal_cards.filter(round_q)
        
        # Фильтрация по локациям - убрано, поля location удалены из модели SignalCard
        
        # Фильтрация по категориям (ИЛИ между собой)
        # Используем ту же логику, что и в GraphQL: Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
        categories_param = request.query_params.get('categories')
        if categories_param:
            category_slugs = [slug.strip() for slug in categories_param.split(',') if slug.strip()]
            if category_slugs:
                # Получаем категории по slugs
                categories = Category.objects.filter(slug__in=category_slugs)
                category_ids = [cat.id for cat in categories]
                
                # Используем ту же логику, что и в GraphQL
                if category_ids:
                    category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
                    signal_cards = signal_cards.filter(category_filter).distinct()
        
        # Фильтрация по участникам (ИЛИ между собой)
        participants_param = request.query_params.get('participants')
        if participants_param:
            participant_slugs = [slug.strip() for slug in participants_param.split(',') if slug.strip()]
            if participant_slugs:
                participants = Participant.objects.filter(slug__in=participant_slugs)
                if participants.exists():
                    participant_ids = list(participants.values_list('id', flat=True))
                    # Фильтруем карточки, где участник или ассоциированный участник в списке
                    participant_signals = Signal.objects.filter(
                        Q(participant_id__in=participant_ids) | Q(associated_participant_id__in=participant_ids),
                        signal_card=OuterRef('pk')
                    )
                    signal_cards = signal_cards.filter(Exists(participant_signals))
        
        # Display preference filtering removed - field doesn't exist in models, treat as ALL
        
        # Search из query_params
        search_param = request.query_params.get('search')
        if search_param:
            signal_cards, _ = apply_search_query_filters(signal_cards, search_param)
        
        # Featured из query_params
        featured_param = request.query_params.get('featured')
        if featured_param is not None:
            featured_value = featured_param.lower() in ('true', '1', 'yes')
            signal_cards = signal_cards.filter(featured=featured_value)
        
        # is_open - игнорируем, это внутренний атрибут, всегда True
        
        # New из query_params
        # new=true → только новые карточки (последние 7 дней)
        # new=false → фильтр не применяется (показываются все карточки)
        new_param = request.query_params.get('new')
        if new_param is not None:
            new_value = new_param.lower() in ('true', '1', 'yes')
            if new_value:
                from datetime import timedelta
                seven_days_ago = timezone.now() - timedelta(days=7)
                # Фильтр для новых карточек (созданных за последние 7 дней)
                signal_cards = signal_cards.filter(created_at__gte=seven_days_ago)
            # Если new=false, фильтр не применяется (показываются все карточки)
        
        # Trending из query_params
        trending_param = request.query_params.get('trending')
        if trending_param is not None:
            trending_value = trending_param.lower() in ('true', '1', 'yes')
            from datetime import timedelta
            one_week_ago = timezone.now() - timedelta(days=7)
            if trending_value:
                signal_cards = signal_cards.filter(
                    interactions_count__gte=5,
                    latest_signal_date__gte=one_week_ago
                )
            else:
                signal_cards = signal_cards.filter(
                    Q(interactions_count__lt=5) | Q(latest_signal_date__lt=one_week_ago) | Q(latest_signal_date__isnull=True)
                )
        
        # Min/Max signals из query_params
        min_signals_param = request.query_params.get('min_signals')
        max_signals_param = request.query_params.get('max_signals')
        if min_signals_param:
            try:
                min_signals = int(min_signals_param)
                signal_cards = signal_cards.filter(interactions_count__gte=min_signals)
            except (ValueError, TypeError):
                pass
        if max_signals_param:
            try:
                max_signals = int(max_signals_param)
                signal_cards = signal_cards.filter(interactions_count__lte=max_signals)
            except (ValueError, TypeError):
                pass
        
        # Применяем distinct() так как interactions_count использует JOIN с signals
        signal_cards = signal_cards.distinct()
        
        # Формируем список полей для сортировки
        order_by_fields = []
        has_latest_signal_date = False
        has_created_at = False
        
        for sort_field in sort_fields:
            # Парсим формат "field:direction"
            if ':' in sort_field:
                parts = sort_field.split(':')
                field_name = parts[0].strip()
                direction = parts[1].strip().lower()
            else:
                # Если direction не указан, используем desc по умолчанию
                field_name = sort_field.strip()
                direction = 'desc'
            
            # Проверяем, что поле разрешено
            if field_name in allowed_sort_fields:
                # Для latest_signal_date используем F() с nulls_last=True (как в GraphQL)
                if field_name == 'latest_signal_date':
                    has_latest_signal_date = True
                    from django.db.models import F
                    if direction == 'desc':
                        order_by_fields.append(F('latest_signal_date').desc(nulls_last=True))
                    else:
                        order_by_fields.append(F('latest_signal_date').asc(nulls_first=True))
                elif field_name == 'created_at':
                    has_created_at = True
                    if direction == 'desc':
                        order_by_fields.append('-created_at')
                    elif direction == 'asc':
                        order_by_fields.append('created_at')
                else:
                    # Для поля name используем name_lower для case-insensitive сортировки
                    if field_name == 'name' and needs_name_lower:
                        sort_field_name = 'name_lower'
                    else:
                        sort_field_name = field_name
                    
                    if direction == 'desc':
                        order_by_fields.append(f'-{sort_field_name}')
                    elif direction == 'asc':
                        order_by_fields.append(sort_field_name)
        
        # Применяем сортировку
        # Если latest_signal_date не указан в сортировке, добавляем его как вторичную сортировку (как в GraphQL)
        if order_by_fields:
            # Если latest_signal_date не указан, добавляем его как вторичную сортировку
            if not has_latest_signal_date:
                from django.db.models import F
                order_by_fields.append(F('latest_signal_date').desc(nulls_last=True))
            # Если created_at не указан, добавляем его как третичную сортировку (как в GraphQL)
            if not has_created_at:
                order_by_fields.append('-created_at')
            signal_cards = signal_cards.order_by(*order_by_fields)
        else:
            # Если сортировка не указана, используем дефолтную (как в GraphQL)
            from django.db.models import F
            signal_cards = signal_cards.order_by(F('latest_signal_date').desc(nulls_last=True), '-created_at')
        
        # Пагинация с limit и offset (с валидацией)
        try:
            limit = int(request.query_params.get('limit', 20))
            limit = min(max(limit, 1), 100)  # Ограничиваем от 1 до 100
        except (ValueError, TypeError):
            limit = 20
        
        try:
            offset = int(request.query_params.get('offset', 0))
            offset = max(offset, 0)  # Ограничиваем минимум 0
        except (ValueError, TypeError):
            offset = 0
        
        # ОПТИМИЗАЦИЯ: Получаем общее количество записей ДО применения limit/offset
        # Но только если нужно (для пагинации). Если не нужна пагинация, можно пропустить.
        # Используем exists() для быстрой проверки наличия следующей страницы вместо count()
        total = signal_cards.count()
        
        # Применяем limit и offset
        signal_cards_page = signal_cards[offset:offset + limit]
        
        # Флаг для включения пользовательских данных
        include_user_data = request.query_params.get('include_user_data', 'false').lower() == 'true'
        
        # Сериализация карточек
        serialized_cards = serialize_card_previews(
            signal_cards=signal_cards_page,
            user=user,
            include_user_data=include_user_data
        )
        
        # Проверяем, есть ли еще записи
        has_next = offset + limit < total
        
        return Response({
            'data': serialized_cards,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': total,
                'has_next': has_next
            }
        })
    
    def post(self, request, *args, **kwargs):
        """
        POST /v1/cards/ - получение списка карт с фильтрами через JSON body
        
        Принимает JSON body с параметрами фильтрации (те же, что и GET параметры).
        Полезно для больших объемов фильтров (тысячи категорий, участников и т.д.).
        
        Пример JSON body:
        {
            "limit": 20,
            "offset": 0,
            "sort": "recent",
            "include_user_data": false,
            "stages": ["seed", "series_a"],
            "rounds": ["raising_now"],
            "categories": ["ai", "saas"],
            "participants": ["investor-fund"],
            "folder_ids": [1, 2, 3],
            "created_after": "2024-01-01",
            "created_before": "2024-12-31"
        }
        """
        # Конвертируем JSON body в словарь параметров
        # Списки конвертируем в строки через запятую
        # None значения не добавляем, чтобы query_params.get() мог вернуть дефолтное значение
        converted_params = {}
        for key, value in request.data.items():
            # Пропускаем None значения
            if value is None:
                continue
            
            if isinstance(value, list):
                # Убираем дубликаты и конвертируем списки в строки через запятую
                unique_values = list(dict.fromkeys(value))  # Сохраняет порядок, убирает дубликаты
                converted_params[key] = ','.join(str(v) for v in unique_values)
            elif isinstance(value, bool):
                # Конвертируем boolean в строку
                converted_params[key] = 'true' if value else 'false'
            else:
                # Остальные значения конвертируем в строку
                converted_params[key] = str(value)
        
        # Создаем простой объект для query_params с методом get()
        class SimpleQueryParams:
            def __init__(self, params):
                self._params = params
            def get(self, key, default=None):
                return self._params.get(key, default)
        
        # Создаем простую обертку для request, которая переопределяет только query_params
        class SimpleRequestWrapper:
            def __init__(self, original_request, query_params_obj):
                self._original = original_request
                self._query_params = query_params_obj
            
            def __getattr__(self, name):
                if name == 'query_params':
                    return self._query_params
                return getattr(self._original, name)
        
        # Передаем параметры через обертку request
        wrapped_request = SimpleRequestWrapper(request, SimpleQueryParams(converted_params))
        return self.get(wrapped_request, *args, **kwargs)


class CardDetailView(ClientAPIView):
    """
    Эндпоинт для получения детальной информации о карточке.
    GET /v1/cards/<slug>/ - получение детальной информации о карточке
    
    Всегда включает до 20 последних взаимодействий (покрывает 95% проектов).
    Для получения всех взаимодействий используйте отдельный эндпоинт /v1/cards/<slug>/interactions/
    
    Параметры запроса:
    - include_user_data: если true, включает пользовательские данные (is_liked, has_note, note, folders) (по умолчанию false)
    """
    
    authentication_classes = [ClientAPITokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, slug, *args, **kwargs):
        """Получает детальную информацию о карточке по slug"""
        user = request.user
        
        # Получаем карточку с предзагрузкой всех связанных данных
        signal_card = self.get_object_or_404_json(
            SignalCard.objects
                .annotate(
                    latest_signal_date=Max('signals__created_at'),
                    oldest_signal_date=Min('signals__created_at')
                )
                .prefetch_related(
                    'categories',
                    'categories__parent_category',
                    'team_members',
                    Prefetch(
                        'signals',
                        queryset=Signal.objects.select_related(
                            'participant',
                            'associated_participant'
                        )
                    )
                )
                .filter(is_open=True),
            slug=slug
        )
        
        # Параметры запроса
        include_user_data = request.query_params.get('include_user_data', 'false').lower() == 'true'
        
        # Сериализуем детальные данные карточки
        # Примечание: всегда включает до 20 последних взаимодействий
        # Для получения всех взаимодействий используйте отдельный эндпоинт /cards/<slug>/interactions/
        card_data = serialize_card_detail(
            signal_card=signal_card,
            user=user,
            include_user_data=include_user_data
        )
        
        return Response({
            'data': card_data
        })


class CardInteractionsView(ClientAPIView):
    """
    Эндпоинт для получения всех взаимодействий карточки с пагинацией.
    GET /v1/cards/<slug>/interactions/ - получение всех взаимодействий
    
    Параметры запроса:
    - limit: количество записей (по умолчанию 50, максимум 200)
    - offset: смещение (по умолчанию 0)
    
    Сортировка: всегда от самых свежих к самым давним (created_at:desc)
    """
    
    def get(self, request, slug, *args, **kwargs):
        """Получает все взаимодействия карточки по slug с пагинацией"""
        user = request.user
        
        # Получаем карточку (проверяем существование и доступность)
        signal_card = self.get_object_or_404_json(
            SignalCard.objects.filter(is_open=True),
            slug=slug
        )
        
        # Пагинация
        try:
            limit = int(request.query_params.get('limit', 50))
            limit = min(max(limit, 1), 200)  # Ограничиваем от 1 до 200
        except (ValueError, TypeError):
            limit = 50
        
        try:
            offset = int(request.query_params.get('offset', 0))
            offset = max(offset, 0)  # Не может быть отрицательным
        except (ValueError, TypeError):
            offset = 0
        
        # Получаем взаимодействия с сортировкой от самых свежих к самым давним
        signals = Signal.objects.filter(
            signal_card=signal_card
        ).select_related(
            'participant',
            'associated_participant'
        ).order_by('-created_at')
        
        # Получаем общее количество для пагинации
        total = signals.count()
        
        # Применяем пагинацию
        signals_page = signals[offset:offset + limit]
        
        # Сериализуем взаимодействия
        serialized_interactions = serialize_interactions(signals_page)
        
        # Проверяем, есть ли еще записи
        has_next = (offset + limit) < total
        
        return Response({
            'data': serialized_interactions,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': total,
                'has_next': has_next
            }
        })


class ParticipantListView(ClientAPIView):
    """
    Эндпоинт для получения списка участников с пагинацией.
    GET /v1/participants/ - получение списка участников
    
    Параметры запроса:
    - limit: количество записей (по умолчанию 50, максимум 200)
    - offset: смещение (по умолчанию 0)
    - search: поиск по имени и описанию (about)
    - type: фильтр по типу участника (fund, investor, etc.)
    - saved_only: если true, показывает только сохраненных участников (по умолчанию false)
    - sort: preset или custom сортировка (по умолчанию 'name')
    - include_user_data: если true, добавляет пользовательские данные (is_saved)
    
    Preset сортировки:
    - name: name:asc (по умолчанию)
    - most_active: monthly_signals:desc,name:asc
    
    Custom сортировка:
    Формат: field:direction,field:direction
    Разрешенные поля: name, monthly_signals
    Направления: asc, desc
    
    Примеры:
    - GET /v1/participants/?sort=name
    - GET /v1/participants/?sort=most_active
    - GET /v1/participants/?sort=monthly_signals:desc,name:asc
    - GET /v1/participants/?search=investor&type=fund
    """
    
    def get(self, request, *args, **kwargs):
        """Получает список участников с пагинацией"""
        user = request.user
        
        # Получаем ID сохраненных участников для доступа к приватным
        saved_participant_ids = set()
        if user.is_authenticated:
            saved_participant_ids = set(SavedParticipant.objects.filter(
                user=user
            ).values_list('participant_id', flat=True))
        
        # Базовый запрос: только публичные участники или сохраненные приватные
        # Предзагружаем associated_with для оптимизации
        participants = Participant.objects.filter(
            # Privacy filtering removed
        ).select_related('associated_with')
        
        # Поиск по имени и описанию
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            participants = participants.filter(
                Q(name__icontains=search_query) | Q(about__icontains=search_query)
            )
        
        # Фильтр по типу
        participant_type = request.query_params.get('type')
        if participant_type:
            participants = participants.filter(type=participant_type)
        
        # Фильтр по сохраненным
        saved_only = request.query_params.get('saved_only', 'false').lower() == 'true'
        if saved_only:
            if not saved_participant_ids:
                # Если нет сохраненных участников, возвращаем пустой список
                return Response({
                    'data': [],
                    'pagination': {
                        'limit': 0,
                        'offset': 0,
                        'total': 0,
                        'has_next': False
                    }
                })
            participants = participants.filter(id__in=saved_participant_ids)
        
        # Сортировка
        sort_param = request.query_params.get('sort', 'name')
        
        # Маппинг между API-именами полей и именами полей в БД
        field_mapping = {
            'monthly_signals': 'monthly_signals_count',  # API имя -> имя в БД
            'name': 'name'
        }
        
        # Preset сортировки (используем API-имена)
        sort_presets = {
            'name': ['name:asc'],
            'most_active': ['monthly_signals:desc', 'name:asc']
        }
        
        # Разрешенные поля для сортировки (API-имена)
        allowed_sort_fields = ['name', 'monthly_signals']
        
        # Парсим параметр сортировки
        if sort_param in sort_presets:
            # Preset сортировка
            sort_fields = sort_presets[sort_param]
        else:
            # Custom сортировка: парсим формат "field:direction,field:direction"
            sort_fields = [s.strip() for s in sort_param.split(',')]
        
        # Проверяем, нужна ли case-insensitive сортировка для name
        needs_name_lower = False
        for sort_field in sort_fields:
            field_name = sort_field.split(':')[0]
            if field_name == 'name':
                needs_name_lower = True  # Для case-insensitive сортировки
                break
        
        # Добавляем аннотацию для case-insensitive сортировки по имени
        if needs_name_lower:
            from django.db.models.functions import Lower
            participants = participants.annotate(name_lower=Lower('name'))
        
        # Формируем список полей для сортировки
        order_by_fields = []
        for sort_field in sort_fields:
            # Парсим формат "field:direction"
            if ':' in sort_field:
                parts = sort_field.split(':')
                field_name = parts[0].strip()
                direction = parts[1].strip().lower()
            else:
                # Если direction не указан, используем asc по умолчанию
                field_name = sort_field.strip()
                direction = 'asc'
            
            # Проверяем, что поле разрешено
            if field_name in allowed_sort_fields:
                # Маппим API-имя на имя поля в БД
                db_field_name = field_mapping.get(field_name, field_name)
                
                # Для поля name используем name_lower для case-insensitive сортировки
                if db_field_name == 'name' and needs_name_lower:
                    sort_field_name = 'name_lower'
                else:
                    sort_field_name = db_field_name
                
                if direction == 'desc':
                    order_by_fields.append(f'-{sort_field_name}')
                elif direction == 'asc':
                    order_by_fields.append(sort_field_name)
        
        # Применяем сортировку
        if order_by_fields:
            participants = participants.order_by(*order_by_fields)
        else:
            # Если сортировка невалидна, используем сортировку по умолчанию
            participants = participants.order_by('name')
        
        # Пагинация
        try:
            limit = int(request.query_params.get('limit', 50))
            limit = min(max(limit, 1), 200)  # Ограничиваем от 1 до 200
        except (ValueError, TypeError):
            limit = 50
        
        try:
            offset = int(request.query_params.get('offset', 0))
            offset = max(offset, 0)  # Не может быть отрицательным
        except (ValueError, TypeError):
            offset = 0
        
        # Параметр для пользовательских данных
        include_user_data = request.query_params.get('include_user_data', 'false').lower() == 'true'
        
        # Получаем общее количество для пагинации
        total = participants.count()
        
        # Применяем пагинацию
        participants_page = participants[offset:offset + limit]
        
        # Сериализуем участников
        serialized_participants = serialize_participants(participants_page, user, include_user_data=include_user_data)
        
        # Проверяем, есть ли еще записи
        has_next = (offset + limit) < total
        
        return Response({
            'data': serialized_participants,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': total,
                'has_next': has_next
            }
        })


class ParticipantBatchView(ClientAPIView):
    """
    Эндпоинт для получения нескольких участников по slugs (batch операция).
    GET /v1/participants/batch/ - получение участников по списку slugs
    
    Параметры запроса:
    - slugs: список slugs через запятую (обязательный)
    - include_user_data: если true, добавляет пользовательские данные (is_saved)
    
    Примеры:
    - GET /v1/participants/batch/?slugs=investor-fund,john-doe,another-fund
    """
    
    def get(self, request, *args, **kwargs):
        """Получает несколько участников по slugs"""
        user = request.user
        
        # Получаем slugs из параметра запроса
        slugs_param = request.query_params.get('slugs', '').strip()
        if not slugs_param:
            return Response({
                'error': 'validation_error',
                'message': 'slugs parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Парсим slugs (разделяем по запятой)
        slugs_list = [slug.strip() for slug in slugs_param.split(',') if slug.strip()]
        
        if not slugs_list:
            return Response({
                'error': 'validation_error',
                'message': 'At least one valid slug is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ограничиваем количество slugs для безопасности
        if len(slugs_list) > 100:
            return Response({
                'error': 'validation_error',
                'message': 'Maximum 100 slugs allowed per request'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Получаем ID сохраненных участников для доступа к приватным
        saved_participant_ids = set()
        if user.is_authenticated:
            saved_participant_ids = set(SavedParticipant.objects.filter(
                user=user
            ).values_list('participant_id', flat=True))
        
        # Получаем участников с проверкой доступа и предзагрузкой связанных данных
        participants = Participant.objects.filter(
            slug__in=slugs_list
        ).filter(
            # Privacy filtering removed
        ).select_related('associated_with').prefetch_related('sources__source_type')
        
        # Параметр для пользовательских данных
        include_user_data = request.query_params.get('include_user_data', 'false').lower() == 'true'
        
        # Сериализуем участников с источниками (для детального ответа)
        participants_data = [
            serialize_participant(p, user, include_sources=True, include_user_data=include_user_data)
            for p in participants
        ]
        
        # Создаем словарь для быстрого доступа по slug
        participants_dict = {p['slug']: p for p in participants_data}
        
        # Возвращаем в том же порядке, что и запрошенные slugs
        ordered_data = []
        for slug in slugs_list:
            if slug in participants_dict:
                ordered_data.append(participants_dict[slug])
        
        return Response({
            'data': ordered_data,
            'requested': len(slugs_list),
            'found': len(ordered_data)
        })


class ParticipantDetailView(ClientAPIView):
    """
    Эндпоинт для получения детальной информации об участнике по slug.
    GET /v1/participants/<slug>/ - получение детальной информации об участнике
    """
    
    def get(self, request, slug, *args, **kwargs):
        """Получает детальную информацию об участнике по slug"""
        user = request.user
        
        # Проверяем доступ к приватным участникам
        saved_participant_ids = set()
        if user.is_authenticated:
            saved_participant_ids = set(SavedParticipant.objects.filter(
                user=user
            ).values_list('participant_id', flat=True))
        
        # Получаем участника с проверкой доступа и предзагрузкой связанных данных
        participant = self.get_object_or_404_json(
            Participant.objects.filter(
                # Privacy filtering removed
            ).select_related('associated_with'),
            slug=slug
        )
        
        # Параметр для пользовательских данных
        include_user_data = request.query_params.get('include_user_data', 'false').lower() == 'true'
        
        # Сериализуем участника с источниками (для детального ответа)
        participant_data = serialize_participant(participant, user, include_sources=True, include_user_data=include_user_data)
        
        return Response({
            'data': participant_data
        })


class ParticipantTypesMetaView(ClientAPIView):
    """
    Эндпоинт для получения списка типов участников.
    GET /v1/participants/types/ - получение типов участников
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает список типов участников"""
        
        # Получаем типы участников из choices
        types = [
            {
                "slug": slug,
                "name": name
            }
            for slug, name in PARTICIPANTS_TYPES
        ]
        
        return Response({
            'data': types
        })


class CardCategoriesMetaView(ClientAPIView):
    """
    Эндпоинт для получения иерархической структуры категорий.
    GET /v1/cards/categories/ - получение категорий
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает иерархическую структуру категорий"""
        # Получаем все родительские категории (без родителя)
        parent_categories = Category.objects.filter(
            parent_category__isnull=True
        ).prefetch_related('children').order_by('name')
        
        # Строим иерархию
        categories_hierarchy = []
        for parent in parent_categories:
            # Получаем дочерние категории
            children = parent.children.all().order_by('name')
            children_list = [
                {
                    "name": child.name,
                    "slug": child.slug
                }
                for child in children
            ]
            
            category_item = {
                "name": parent.name,
                "slug": parent.slug,
                "categories": children_list if children_list else []
            }
            
            categories_hierarchy.append(category_item)
        
        return Response({
            'data': categories_hierarchy
        })


class CardStagesMetaView(ClientAPIView):
    """
    Эндпоинт для получения списка стадий.
    GET /v1/cards/stages/ - получение стадий
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает список стадий"""
        stages = [
            {
                "slug": slug,
                "name": name
            }
            for slug, name in STAGES
        ]
        
        return Response({
            'data': stages
        })


class CardRoundsMetaView(ClientAPIView):
    """
    Эндпоинт для получения списка раундов.
    GET /v1/cards/rounds/ - получение раундов
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает список раундов"""
        rounds = [
            {
                "slug": slug,
                "name": name
            }
            for slug, name in ROUNDS
        ]
        
        return Response({
            'data': rounds
        })


class CardFoldersMetaView(ClientAPIView):
    """
    Эндпоинт для получения списка папок пользователя (мета-данные для карточек).
    GET /v1/cards/folders/ - получение списка папок пользователя
    
    Возвращает список папок пользователя с базовой информацией:
    - id: ID папки (используется для фильтрации в folder_ids)
    - name: Название папки
    - is_default: Является ли папка папкой по умолчанию
    - cards_count: Количество карточек в папке
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает список папок пользователя"""
        user = request.user
        
        # Получаем все папки пользователя с количеством карточек
        folders = UserFolder.objects.filter(user=user)\
            .annotate(cards_count=Count('folder_cards'))\
            .order_by('-is_default', 'name')\
            .values('id', 'name', 'is_default', 'cards_count')
        
        folders_list = list(folders)
        
        return Response({
            'data': folders_list
        })


class CardFiltersMetaView(ClientAPIView):
    """
    Эндпоинт для получения списка сохраненных фильтров пользователя (мета-данные для карточек).
    GET /v1/cards/filters/ - получение списка сохраненных фильтров пользователя
    
    Возвращает упрощенный список сохраненных фильтров пользователя:
    - id: ID фильтра (используется для применения через filter_id)
    - name: Название фильтра
    
    Внутренние параметры фильтрации не отображаются. Для применения фильтра используйте filter_id в запросе /v1/cards/.
    """
    
    def get(self, request, *args, **kwargs):
        """Возвращает список сохраненных фильтров пользователя (только id и name)"""
        user = request.user
        
        # Получаем все сохраненные фильтры пользователя
        saved_filters = SavedFilter.objects.filter(user=user)\
            .order_by('-is_default', '-updated_at', 'name')
        
        filters_list = []
        for saved_filter in saved_filters:
            filters_list.append({
                'id': saved_filter.id,
                'name': saved_filter.name
            })
        
        return Response({
            'data': filters_list
        })