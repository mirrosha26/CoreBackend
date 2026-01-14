from django.db.models import Q, Max, Min, Count, Case, When, Exists, OuterRef
from django.core.paginator import Paginator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch
import datetime

from signals.models import SignalCard, Signal
from profile.models import UserFolder, FolderCard, DeletedCard, UserFeed, SavedParticipant
from signals.models import Participant

from frontend_api.views.utils import apply_search_query_filters, get_date_range, apply_signal_count_filters
from frontend_api.serializers.cards.previews import serialize_previews

def sync_user_feed_with_saved_participants(user):
    """
    Синхронизирует UserFeed с SavedParticipant для обеспечения согласованности.
    """
    # Получаем или создаем UserFeed
    user_feed, created = UserFeed.objects.get_or_create(user=user)
    
    # Получаем ID сохраненных участников
    saved_participant_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
    
    # Получаем ID участников в UserFeed
    feed_participant_ids = user_feed.participants.values_list('id', flat=True)
    
    # Проверяем, нужна ли синхронизация
    if set(saved_participant_ids) != set(feed_participant_ids):
        # Обновляем участников в UserFeed
        participants = Participant.objects.filter(id__in=saved_participant_ids)
        user_feed.participants.set(participants)
        user_feed.save()

class BaseSignalFilterView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_base_queryset(self, user):
        # Оптимизируем базовый QuerySet
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
        
        # Оптимизируем фильтр по приватности
        private_participant_filter = Q(
            signals__associated_participant__saved_by_users__user=user
        )
        # Privacy filtering removed
        signal_cards = signal_cards.filter(private_participant_filter | non_private_participant_filter)
        
        return signal_cards
    
    def apply_common_filters(self, signal_cards, request, user):
        # Получаем все необходимые параметры фильтрации из GET-запроса
        search_query = request.query_params.get('search', '').strip()
        last_week = request.query_params.get('last_week', 'false').lower() == 'true'
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        hide_liked = request.query_params.get('hide_liked', 'false').lower() == 'true'
        
        min_sig = int(request.query_params.get('min_sig', 1))
        max_sig = request.query_params.get('max_sig')
        if max_sig:
            max_sig = int(max_sig)
            
        # Оптимизируем получение ID для saved/deleted карточек
        default_folder = UserFolder.objects.filter(user=user, is_default=True).first()
        saved_ids = set()

        # Получаем все ID карточек, которые находятся в любой папке пользователя
        if hide_liked and default_folder:
            saved_ids = set(FolderCard.objects.filter(
                folder=default_folder,
                folder__user=user
            ).values_list('signal_card_id', flat=True))
        
        deleted_ids = set(DeletedCard.objects.filter(user=user).values_list('signal_card_id', flat=True))
        
        # Применяем базовые фильтры исключения
        signal_cards = signal_cards.exclude(id__in=deleted_ids)
        if hide_liked:
            signal_cards = signal_cards.exclude(id__in=saved_ids)
        
        # Применяем поисковый запрос
        using_search_relevance_sort = False
        if search_query:
            signal_cards, using_search_relevance_sort = apply_search_query_filters(signal_cards, search_query)
            # Добавляем аннотацию latest_signal_date к результатам поиска
            if using_search_relevance_sort and hasattr(signal_cards, 'annotate'):
                signal_cards = signal_cards.annotate(latest_signal_date=Max('signals__created_at'))
        
        # Добавляем фильтрацию по количеству сигналов
        signal_cards = apply_signal_count_filters(signal_cards, min_sig, max_sig)

        # Применяем фильтр по времени
        if last_week:
            last_week_start, last_week_end = get_date_range('last_week')
            if last_week_start and last_week_end:
                signal_cards = signal_cards.filter(created_at__range=(last_week_start, last_week_end))

        # Применяем distinct() до аннотации latest_signal_date
        if hasattr(signal_cards, 'distinct'):
            signal_cards = signal_cards.distinct()
        
        # Применяем аннотацию latest_signal_date только если signal_cards - QuerySet и не было поискового запроса
        if hasattr(signal_cards, 'annotate') and not search_query:
            signal_cards = signal_cards.annotate(
                latest_signal_date=Max('signals__created_at')
            )
        
        # Применяем фильтр по диапазону дат после аннотации
        if start_date and hasattr(signal_cards, 'filter'):
            try:
                start_datetime = datetime.datetime.strptime(start_date, '%d.%m.%Y')
                if end_date:
                    end_datetime = datetime.datetime.strptime(end_date, '%d.%m.%Y')
                    end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                    date_filter = {'latest_signal_date__range': (start_datetime, end_datetime)}
                else:
                    date_filter = {'latest_signal_date__gte': start_datetime}
                signal_cards = signal_cards.filter(**date_filter)
            except ValueError:
                return None, {
                    'success': False,
                    'error': 'INVALID_DATE_FORMAT',
                    'message': 'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                }, status.HTTP_400_BAD_REQUEST
        
        # Применяем сортировку после всех фильтров
        if hasattr(signal_cards, 'order_by'):
            if using_search_relevance_sort:
                # Если был поисковый запрос, сортируем по релевантности (от большей к меньшей)
                signal_cards = signal_cards.order_by('-search_relevance', '-latest_signal_date')
            else:
                # Иначе сортируем по дате
                signal_cards = signal_cards.order_by('-latest_signal_date')
                
        return signal_cards, None, None
    
    def apply_specific_filters(self, signal_cards, request, user):
        """
        Применяет специфичные фильтры на основе настроек пользователя и типа представления.
        Должен быть переопределен в дочерних классах.
        """
        # Базовый класс не применяет никаких специфичных фильтров
        return signal_cards
    
    def paginate_queryset(self, signal_cards, request):
        # Пагинация
        page_size = int(request.query_params.get('page_size', 20))
        paginator = Paginator(signal_cards, page_size)
        page_number = request.query_params.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        return page_obj, paginator, int(page_number)
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Получаем базовый QuerySet
        signal_cards = self.get_base_queryset(user)
        
        # Применяем специфичные фильтры (переопределяется в дочерних классах)
        signal_cards = self.apply_specific_filters(signal_cards, request, user)
        
        # Применяем общие фильтры на основе GET-параметров
        signal_cards, error_response, error_status = self.apply_common_filters(signal_cards, request, user)
        if error_response:
            return Response(error_response, status=error_status)
        
        # Пагинация
        page_obj, paginator, page_number = self.paginate_queryset(signal_cards, request)
        
        # Сериализация
        serialized_cards = serialize_previews(
            signal_cards=page_obj.object_list,
            user=user
        )
        
        return Response({
            'success': True,
            'loadMore': page_obj.has_next(),
            'cards': serialized_cards,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_number
        })


class AllSignalsView(BaseSignalFilterView):
    def apply_specific_filters(self, signal_cards, request, user):
        # Исключаем карточки со стадией 'worth_following' - это специфика AllSignalsView
        signal_cards = signal_cards.exclude(stage='worth_following')
        
        # Применяем фильтрацию в соответствии с предпочтениями пользователя
        if False:  # Удалено: всегда показываем все
            # Показываем только сигналы с категорией web3 или её дочерними категориями
            from signals.models import Category
            web3_category = Category.objects.filter(slug='web3').first()
            if web3_category:
                web3_subcategories = Category.objects.filter(parent_category=web3_category).values_list('id', flat=True)
                signal_cards = signal_cards.filter(Q(categories__slug='web3') | Q(categories__id__in=web3_subcategories))
            else:
                signal_cards = signal_cards.filter(categories__slug='web3')
        elif False:  # Удалено: всегда показываем все
            # Исключаем сигналы с категорией web3
            signal_cards = signal_cards.exclude(categories__slug='web3')
        
        # Применяем фильтры из сессии, если они есть
        session_filters = request.session.get('current_filters', {})
        
        if session_filters.get('categories'):
            from signals.models import Category
            category_ids = [int(c) for c in session_filters['categories']]
            signal_cards = signal_cards.filter(categories__id__in=category_ids)

        if session_filters.get('participants'):
            from signals.models import Participant
            participant_ids = [int(p) for p in session_filters['participants']]
            signal_cards = signal_cards.filter(
                Q(signals__participant_id__in=participant_ids) |
                Q(signals__associated_participant_id__in=participant_ids)
            )

        if session_filters.get('round_statuses') or session_filters.get('stages'):
            stages_rounds_filter = Q()
            if session_filters.get('round_statuses'):
                stages_rounds_filter |= Q(round_status__in=session_filters['round_statuses'])
            if session_filters.get('stages'):
                # Ensure worth_following is not included in stages filter
                stages = [stage for stage in session_filters['stages'] if stage != 'worth_following']
                if stages:
                    stages_rounds_filter |= Q(stage__in=stages)
            if stages_rounds_filter:
                signal_cards = signal_cards.filter(stages_rounds_filter)
                
        return signal_cards


class UserFeedView(BaseSignalFilterView):
    """
    Представление для получения ленты пользователя на основе его подписок на участников.
    """
    def apply_specific_filters(self, signal_cards, request, user):
        # Исключаем карточки со стадией 'worth_following' - это специфика UserFeedView
        signal_cards = signal_cards.exclude(stage='worth_following')
        
        # Всегда показываем все сигналы (ALL)
        
        # Синхронизируем UserFeed с SavedParticipant для обеспечения согласованности
        sync_user_feed_with_saved_participants(user)
        
        # Получаем или создаем UserFeed в одном запросе
        user_feed, created = UserFeed.objects.select_related(
            'user'
        ).prefetch_related(
            'categories',
            'participants'
        ).get_or_create(user=user)
        
        # Проверяем, следит ли пользователь за какими-либо инвесторами
        if not user_feed.participants.exists():
            # Проверяем, есть ли у пользователя сохраненные участники
            has_saved_participants = SavedParticipant.objects.filter(user=user).exists()
            if has_saved_participants:
                # У пользователя есть сохраненные участники, но их нет в UserFeed, синхронизируем их
                saved_participant_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
                participants = Participant.objects.filter(id__in=saved_participant_ids)
                user_feed.participants.set(participants)
                user_feed.save()
            else:
                # Возвращаем пустой QuerySet
                return signal_cards.none()
        
        # Применяем фильтры из UserFeed
        if user_feed.categories.exists():
            # Получаем список ID категорий вместо использования ManyRelatedManager
            category_ids = list(user_feed.categories.values_list('id', flat=True))
            signal_cards = signal_cards.filter(
                Q(categories__id__in=category_ids) | 
                Q(categories__parent_category__id__in=category_ids)
            )
        
        if user_feed.participants.exists():
            participant_ids = list(user_feed.participants.values_list('id', flat=True))
            signal_cards = signal_cards.filter(
                Q(signals__participant_id__in=participant_ids) |
                Q(signals__associated_participant_id__in=participant_ids)
            )
        
        # Применяем фильтры по стадиям и раундам
        stages_rounds_filter = Q()
        if user_feed.round_statuses:
            stages_rounds_filter |= Q(round_status__in=list(user_feed.round_statuses))
        if user_feed.stages:
            # Исключаем worth_following из фильтра по стадиям
            stages = [stage for stage in list(user_feed.stages) if stage != 'worth_following']
            if stages:
                stages_rounds_filter |= Q(stage__in=stages)
        
        if user_feed.round_statuses or user_feed.stages:
            signal_cards = signal_cards.filter(stages_rounds_filter)
        
        return signal_cards
    
    # Метод get не переопределяем, используем из базового класса

class WorthFollowingView(BaseSignalFilterView):
    """
    Представление для получения карточек со стадией 'worth_following'.
    """
    def get_base_queryset(self, user):
        # Получаем базовый QuerySet с учетом приватности (используем родительский метод)
        signal_cards = super().get_base_queryset(user)
        
        # Добавляем аннотации для дат сигналов
        signal_cards = signal_cards.annotate(
            latest_signal_date=Max('signals__created_at'),
            oldest_signal_date=Min('signals__created_at')
        )
        
        # Фильтруем только карточки со стадией 'worth_following'
        signal_cards = signal_cards.filter(stage='worth_following')
        
        # Добавляем дополнительные prefetch_related
        signal_cards = signal_cards.prefetch_related(
            'team_members',
            'tags'
        )
        
        return signal_cards
    
    def apply_specific_filters(self, signal_cards, request, user):
        # Применяем фильтрацию в соответствии с предпочтениями пользователя
        if False:  # Удалено: всегда показываем все
            # Показываем только сигналы с категорией web3 или её дочерними категориями
            from signals.models import Category
            web3_category = Category.objects.filter(slug='web3').first()
            if web3_category:
                web3_subcategories = Category.objects.filter(parent_category=web3_category).values_list('id', flat=True)
                signal_cards = signal_cards.filter(Q(categories__slug='web3') | Q(categories__id__in=web3_subcategories))
            else:
                signal_cards = signal_cards.filter(categories__slug='web3')
        elif False:  # Удалено: всегда показываем все
            # Исключаем сигналы с категорией web3
            signal_cards = signal_cards.exclude(categories__slug='web3')
        
        # WorthFollowingFilter model has been removed
        
        return signal_cards