import logging
from datetime import datetime, time
from typing import List, Optional

import strawberry
import strawberry_django
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import (
    Q, Max, Min, Count, Prefetch, Exists, OuterRef, F, When, Case, Subquery
)
from django.utils import timezone

from profile.models import (
    UserNote, FolderCard, DeletedCard, UserFolder, UserFeed, SavedParticipant,
    SavedFilter as SavedFilterModel, GroupAssignedCard
)
from signals.models import SignalCard, Signal, Category, Participant, STAGES, ROUNDS
from signals.utils import apply_search_query_filters

from .dataloaders import get_dataloader_manager
from .performance import monitor_query_performance
from .query_complexity import analyze_query_complexity, validate_query_complexity
from .types import (
    User, SignalCard as SignalCardType, SignalCardConnection,
    SignalCardFilters, PaginationInput, Category as CategoryType,
    Participant as ParticipantType, ParticipantConnection, PageInfo,
    ParticipantRelayConnection, ParticipantEdge, CardType, SortBy, SortOrder,
    StageFilter, RoundFilter, FilterStats, SignalCardFiltersOutput,
    SavedFilter, SavedFilterConnection, SavedFilterListResult,
    ParticipantFilterMode,
    GroupAssignedCardConnection, GroupAssignedCardGraphQL, AssignmentStatus,
    AssignmentFilterType
)

logger = logging.getLogger(__name__)


def _get_optimized_signal_cards_queryset(user=None, include_signals=True, display_preference=None):
    """
    Получает оптимизированный базовый queryset для SignalCards с улучшенной защитой от N+1.
    
    Args:
        user: Объект пользователя (не используется, оставлено для совместимости)
        include_signals: Предзагружать ли сигналы
        display_preference: Не используется (всегда ALL), оставлено для совместимости
    """
    enhanced_prefetch = [
        'categories',
        'team_members',
    ]
    
    if include_signals:
        enhanced_prefetch.extend([
            'signals__participant',
            'signals__associated_participant',
            'signals__signal_type',
        ])
    
    queryset = SignalCard.objects.prefetch_related(*enhanced_prefetch)
    
    queryset = queryset.annotate(
        latest_signal_date=Max('signals__created_at')
    )
    
    # Всегда показываем все сигналы (ALL)
    return queryset


def _serialize_filters_for_cache(filters):
    """
    Сериализует фильтры для кэширования, преобразуя объекты дат в строки.
    
    Args:
        filters: Объект SignalCardFilters или None
        
    Returns:
        Словарь с сериализованными значениями фильтров или None, если filters is None
    """
    if not filters:
        return None
    
    participant_filter_serialized = None
    if filters.participant_filter:
        participant_filter_serialized = {
            'mode': filters.participant_filter.mode.value,
            'participant_ids': filters.participant_filter.participantIds,
            'participant_types': filters.participant_filter.participantTypes
        }
    
    return {
        'search': filters.search,
        'categories': filters.categories,
        'participants': filters.participants,
        'participant_filter': participant_filter_serialized,
        'stages': filters.stages,
        'round_statuses': filters.round_statuses,
        'featured': filters.featured,
        'is_open': filters.is_open,
        'new': filters.new,
        'trending': filters.trending,
        'min_signals': filters.min_signals,
        'max_signals': filters.max_signals,
        'start_date': filters.start_date.isoformat() if filters.start_date else None,
        'end_date': filters.end_date.isoformat() if filters.end_date else None,
        'hide_liked': filters.hide_liked,
        'show_old': filters.show_old
    }


def _apply_optimized_filters(queryset, filters, user=None):
    """
    Применяет фильтры эффективно с оптимизациями на уровне БД.
    
    Returns:
        Кортеж: (queryset, has_search_relevance) - где has_search_relevance указывает,
               применена ли аннотация релевантности поиска для сортировки
    """
    if not filters:
        return queryset, False
    
    from django.utils import timezone
    from datetime import datetime, time
    
    has_search_relevance = False
    
    if filters.search:
        queryset, has_search_relevance = apply_search_query_filters(queryset, filters.search)
    
    if filters.categories:
        category_ids = [int(cat_id) for cat_id in filters.categories]
        category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
        queryset = queryset.filter(category_filter)
    
    if filters.participant_filter:
        participant_filter = filters.participant_filter
        mode = participant_filter.mode
        participant_ids = [int(p_id) for p_id in participant_filter.participantIds] if participant_filter.participantIds else []
        participant_types = participant_filter.participantTypes or []
        
        legacy_participant_ids = []
        if filters.participants:
            legacy_participant_ids = [int(p_id) for p_id in filters.participants]
        
        if mode == ParticipantFilterMode.INCLUDE_ONLY:
            all_included_ids = participant_ids + legacy_participant_ids
            if all_included_ids:
                participant_signals = Signal.objects.filter(
                    Q(participant_id__in=all_included_ids) |
                    Q(associated_participant_id__in=all_included_ids),
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.filter(Exists(participant_signals))
        elif mode == ParticipantFilterMode.EXCLUDE_FROM_TYPE:
            if participant_types:
                filter_conditions = Q()
                
                type_filter = Q(
                    Q(participant__type__in=participant_types) |
                    Q(associated_participant__type__in=participant_types)
                )
                
                if participant_ids:
                    type_filter &= ~(
                        Q(participant_id__in=participant_ids) |
                        Q(associated_participant_id__in=participant_ids)
                    )
                
                filter_conditions |= type_filter
                
                if legacy_participant_ids:
                    legacy_filter = Q(
                        Q(participant_id__in=legacy_participant_ids) |
                        Q(associated_participant_id__in=legacy_participant_ids)
                    )
                    filter_conditions |= legacy_filter
                
                participant_signals = Signal.objects.filter(
                    filter_conditions,
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.filter(Exists(participant_signals))
            elif legacy_participant_ids:
                participant_signals = Signal.objects.filter(
                    Q(participant_id__in=legacy_participant_ids) |
                    Q(associated_participant_id__in=legacy_participant_ids),
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.filter(Exists(participant_signals))
    elif filters.participants:
        participant_ids = [int(p_id) for p_id in filters.participants]
        participant_signals = Signal.objects.filter(
            Q(participant_id__in=participant_ids) |
            Q(associated_participant_id__in=participant_ids),
            signal_card=OuterRef('pk')
        )
        queryset = queryset.filter(Exists(participant_signals))
    
    if filters.stages:
        queryset = queryset.filter(stage__in=filters.stages)
    
    if filters.round_statuses:
        queryset = queryset.filter(round_status__in=filters.round_statuses)
    
    if filters.featured is not None:
        queryset = queryset.filter(featured=filters.featured)
    
    if filters.is_open is not None:
        queryset = queryset.filter(is_open=filters.is_open)
    
    if filters.new is not None and filters.new:
        from datetime import timedelta
        seven_days_ago = timezone.now() - timedelta(days=7)
        queryset = queryset.filter(created_at__gte=seven_days_ago)
    if filters.trending is not None:
        from datetime import timedelta
        from collections import defaultdict
        
        one_week_ago = timezone.now() - timedelta(days=7)
        
        recent_signal_query = Signal.objects.filter(
            created_at__gte=one_week_ago
        ).filter(
            Q(participant__isnull=False) | Q(associated_participant__isnull=False)
        )
        if filters.participant_filter:
            participant_filter = filters.participant_filter
            mode = participant_filter.mode
            participant_ids = [int(p_id) for p_id in participant_filter.participantIds] if participant_filter.participantIds else []
            participant_types = participant_filter.participantTypes or []
            
            # Collect legacy participant IDs
            legacy_participant_ids = []
            if filters.participants:
                legacy_participant_ids = [int(p_id) for p_id in filters.participants]
            
            if mode == ParticipantFilterMode.INCLUDE_ONLY:
                all_included_ids = participant_ids + legacy_participant_ids
                if all_included_ids:
                    recent_signal_query = recent_signal_query.filter(
                        Q(participant_id__in=all_included_ids) | 
                        Q(associated_participant_id__in=all_included_ids)
                    )
            elif mode == ParticipantFilterMode.EXCLUDE_FROM_TYPE:
                if participant_types:
                    filter_conditions = Q()
                    type_filter = Q(
                        Q(participant__type__in=participant_types) | 
                        Q(associated_participant__type__in=participant_types)
                    )
                    if participant_ids:
                        type_filter &= ~(
                            Q(participant_id__in=participant_ids) | 
                            Q(associated_participant_id__in=participant_ids)
                        )
                    filter_conditions |= type_filter
                    if legacy_participant_ids:
                        filter_conditions |= Q(
                            Q(participant_id__in=legacy_participant_ids) | 
                            Q(associated_participant_id__in=legacy_participant_ids)
                        )
                    recent_signal_query = recent_signal_query.filter(filter_conditions)
                elif legacy_participant_ids:
                    recent_signal_query = recent_signal_query.filter(
                        Q(participant_id__in=legacy_participant_ids) | 
                        Q(associated_participant_id__in=legacy_participant_ids)
                    )
        elif filters.participants:
            participant_ids = [int(p_id) for p_id in filters.participants]
            recent_signal_query = recent_signal_query.filter(
                Q(participant_id__in=participant_ids) | 
                Q(associated_participant_id__in=participant_ids)
            )
        
        # Apply privacy filtering and get all distinct combinations for recent signals
        recent_combinations = recent_signal_query.filter(
            # Privacy filtering removed - all participants are accessible
            Q(
                participant__isnull=False
            ) | Q(
                associated_participant__isnull=False
            )
        ).values(
            'signal_card', 'participant_id', 'associated_participant_id'
        ).distinct()
        
        # Count distinct participant/linkedin_data pairs per signal_card in Python (same as min_signals)
        recent_signal_card_counts = defaultdict(int)
        for combo in recent_combinations:
            recent_signal_card_counts[combo['signal_card']] += 1
        
        # Get signal cards with trending status (5+ unique participant pairs in last week)
        trending_card_ids = [
            signal_card_id for signal_card_id, count in recent_signal_card_counts.items()
            if count >= 5
        ]
        
        if filters.trending:
            # Filter for trending projects
            queryset = queryset.filter(id__in=trending_card_ids)
        else:
            # Filter for non-trending projects
            queryset = queryset.exclude(id__in=trending_card_ids)
    
    # Date range filters - convert dates to timezone-aware datetimes
    # When show_old=True: filter by latest_signal_date and exclude cards created in date range
    # When show_old=False or None: use default behavior (filter by created_at)
    if filters.show_old:
        # PERFORMANCE FIX: Instead of filtering on the expensive latest_signal_date annotation,
        # use EXISTS with a subquery on signals table which is much faster
        if filters.start_date and filters.end_date:
            # Convert dates to timezone-aware datetimes
            start_datetime = timezone.make_aware(datetime.combine(filters.start_date, time.min))
            end_datetime = timezone.make_aware(datetime.combine(filters.end_date, time.max))
            
            # Filter cards that have at least one signal in the date range
            # This is MUCH faster than filtering on the aggregated latest_signal_date
            signals_in_range = Signal.objects.filter(
                signal_card=OuterRef('pk'),
                created_at__range=(start_datetime, end_datetime)
            )
            queryset = queryset.filter(Exists(signals_in_range))
            
            # Exclude cards created in the date range (keep only old cards with new signals)
            queryset = queryset.exclude(
                created_at__range=(start_datetime, end_datetime)
            )
        elif filters.start_date:
            start_datetime = timezone.make_aware(datetime.combine(filters.start_date, time.min))
            signals_in_range = Signal.objects.filter(
                signal_card=OuterRef('pk'),
                created_at__gte=start_datetime
            )
            queryset = queryset.filter(Exists(signals_in_range))
            queryset = queryset.exclude(created_at__gte=start_datetime)
        elif filters.end_date:
            end_datetime = timezone.make_aware(datetime.combine(filters.end_date, time.max))
            signals_in_range = Signal.objects.filter(
                signal_card=OuterRef('pk'),
                created_at__lte=end_datetime
            )
            queryset = queryset.filter(Exists(signals_in_range))
            queryset = queryset.exclude(created_at__lte=end_datetime)
    else:
        # Default behavior: filter by created_at
        if filters.start_date and filters.end_date:
            # Convert dates to timezone-aware datetimes
            start_datetime = timezone.make_aware(datetime.combine(filters.start_date, time.min))
            end_datetime = timezone.make_aware(datetime.combine(filters.end_date, time.max))
            queryset = queryset.filter(
                created_at__range=(start_datetime, end_datetime)
            )
        elif filters.start_date:
            start_datetime = timezone.make_aware(datetime.combine(filters.start_date, time.min))
            queryset = queryset.filter(created_at__gte=start_datetime)
        elif filters.end_date:
            end_datetime = timezone.make_aware(datetime.combine(filters.end_date, time.max))
            queryset = queryset.filter(created_at__lte=end_datetime)
    
    # Signal count filters - use privacy-aware signal counting with database-level aggregation
    # CRITICAL: This optimization prevents memory exhaustion for accounts with many follows
    # Performance: Uses database COUNT DISTINCT instead of fetching millions of records into Python memory
    if filters.min_signals or filters.max_signals:
        # Import required modules for database aggregation
        import time as time_module
        
        # Privacy filter removed - all signals are accessible
        privacy_filter = Q(
            Q(participant__isnull=False) | 
            Q(associated_participant__isnull=False)
        )
        
        # Build participant filter for signal queries
        participant_signal_filter = Q(participant__isnull=False) | Q(associated_participant__isnull=False)
        
        # Apply participant filtering from current filters
        if filters.participant_filter:
            participant_filter = filters.participant_filter
            mode = participant_filter.mode
            participant_ids = [int(p_id) for p_id in participant_filter.participantIds] if participant_filter.participantIds else []
            participant_types = participant_filter.participantTypes or []
            
            # Collect legacy participant IDs
            legacy_participant_ids = []
            if filters.participants:
                legacy_participant_ids = [int(p_id) for p_id in filters.participants]
            
            if mode == ParticipantFilterMode.INCLUDE_ONLY:
                all_included_ids = participant_ids + legacy_participant_ids
                if all_included_ids:
                    participant_signal_filter = Q(
                        Q(participant_id__in=all_included_ids) | 
                        Q(associated_participant_id__in=all_included_ids)
                    )
            elif mode == ParticipantFilterMode.EXCLUDE_FROM_TYPE:
                if participant_types:
                    filter_conditions = Q()
                    type_filter = Q(
                        Q(participant__type__in=participant_types) | 
                        Q(associated_participant__type__in=participant_types)
                    )
                    if participant_ids:
                        type_filter &= ~(
                            Q(participant_id__in=participant_ids) | 
                            Q(associated_participant_id__in=participant_ids)
                        )
                    filter_conditions |= type_filter
                    if legacy_participant_ids:
                        filter_conditions |= Q(
                            Q(participant_id__in=legacy_participant_ids) | 
                            Q(associated_participant_id__in=legacy_participant_ids)
                        )
                    participant_signal_filter = filter_conditions
                elif legacy_participant_ids:
                    participant_signal_filter = Q(
                        Q(participant_id__in=legacy_participant_ids) | 
                        Q(associated_participant_id__in=legacy_participant_ids)
                    )
        elif filters.participants:
            participant_ids = [int(p_id) for p_id in filters.participants]
            participant_signal_filter = Q(
                Q(participant_id__in=participant_ids) | 
                Q(associated_participant_id__in=participant_ids)
            )
        
        # Use database-level aggregation for MASSIVE performance improvement
        # This avoids fetching potentially millions of signal combinations into Python memory
        
        # Apply signal count filters using efficient database aggregation
        # Performance monitoring: This should be orders of magnitude faster than the old approach
        start_time = time_module.time()
        
        if filters.min_signals:
            # Count accessible signals per card using subquery and filter cards with enough signals
            accessible_signal_count_subquery = Signal.objects.filter(
                signal_card=OuterRef('pk')
            ).filter(
                participant_signal_filter & privacy_filter
            ).values('signal_card').annotate(
                unique_count=Count(
                    Case(
                        When(participant__isnull=False, then='participant_id'),
                        When(associated_participant__isnull=False, then='associated_participant_id'),
                        default=None
                    ),
                    distinct=True
                )
            ).values('unique_count')
            
            queryset = queryset.annotate(
                accessible_signal_count=Subquery(accessible_signal_count_subquery)
            ).filter(accessible_signal_count__gte=filters.min_signals)
        
        if filters.max_signals:
            # Count accessible signals per card using subquery and filter cards within max signals
            if not filters.min_signals:  # Avoid double annotation
                accessible_signal_count_subquery = Signal.objects.filter(
                    signal_card=OuterRef('pk')
                ).filter(
                    participant_signal_filter & privacy_filter
                ).values('signal_card').annotate(
                    unique_count=Count(
                        Case(
                            When(participant__isnull=False, then='participant_id'),
                            When(associated_participant__isnull=False, then='associated_participant_id'),
                            default=None
                        ),
                        distinct=True
                    )
                ).values('unique_count')
                
                queryset = queryset.annotate(
                    accessible_signal_count=Subquery(accessible_signal_count_subquery)
                )
            
            queryset = queryset.filter(accessible_signal_count__lte=filters.max_signals)
        
        # Log performance improvement
        filter_time = time_module.time() - start_time
        if filter_time > 0.1:  # Log slow queries
            logger.warning(f"Signal count filter took {filter_time:.3f}s for user {user.id if user else 'anon'}")
        else:
            logger.debug(f"Signal count filter completed in {filter_time:.3f}s")
    
    # Hide liked cards filter
    if filters.hide_liked is not None and filters.hide_liked and user and user.is_authenticated:
        # Exclude cards that are favorited by the user (in any folder)
        liked_cards = FolderCard.objects.filter(
            folder__user=user,
            signal_card=OuterRef('pk')
        )
        queryset = queryset.exclude(Exists(liked_cards))
    
    return queryset.distinct(), has_search_relevance


def _filter_cards_with_accessible_signals(queryset, user, applied_filters=None):
    """
    ВАЖНО: Фильтрует карточки, у которых нет доступных сигналов после фильтрации приватности.
    Должен совпадать с той же логикой приватности, что используется в резолвере сигналов.
    
    Args:
        queryset: Queryset для фильтрации
        user: Аутентифицированный пользователь
        applied_filters: Фильтры, примененные в _apply_optimized_filters для сохранения фильтрации участников
    """
    # Build privacy filter that allows:
    # 1. All public participants (regardless of feed status)
    # 2. Private participants only if saved by user
    # 3. LinkedIn data signals (always accessible)
    # 4. Founder signals (always accessible)
    # 5. CRITICAL: Only signals that actually have participants, LinkedIn data, or source signal card
    accessible_signals = Signal.objects.filter(
        signal_card=OuterRef('pk')
    ).filter(
        # Must have at least one participant (either main or associated)
        Q(participant__isnull=False) | Q(associated_participant__isnull=False)
    )
    
    # CRITICAL: Apply participant filtering from _apply_optimized_filters first
    if applied_filters and applied_filters.participant_filter:
        participant_filter = applied_filters.participant_filter
        mode = participant_filter.mode
        participant_ids = [int(p_id) for p_id in participant_filter.participantIds] if participant_filter.participantIds else []
        participant_types = participant_filter.participantTypes or []
        
        # Collect legacy participant IDs to include alongside advanced filtering
        legacy_participant_ids = []
        if applied_filters.participants:
            legacy_participant_ids = [int(p_id) for p_id in applied_filters.participants]
        
        if mode == ParticipantFilterMode.INCLUDE_ONLY:
            # Only show signals from these specific participants (combine both sources)
            all_included_ids = participant_ids + legacy_participant_ids
            if all_included_ids:
                accessible_signals = accessible_signals.filter(
                    Q(participant_id__in=all_included_ids) | 
                    Q(associated_participant_id__in=all_included_ids)
                )
        elif mode == ParticipantFilterMode.EXCLUDE_FROM_TYPE:
            # CORRECTED LOGIC: Include participants of specified types, exclude specific IDs, plus legacy participants
            if participant_types:
                # Build the filter conditions
                filter_conditions = Q()
                
                # 1. Include signals from participants of specified types, excluding specific IDs
                type_filter = Q(
                    Q(participant__type__in=participant_types) | 
                    Q(associated_participant__type__in=participant_types)
                )
                
                # Exclude specific participant IDs from the type selection if provided
                if participant_ids:
                    type_filter &= ~(
                        Q(participant_id__in=participant_ids) | 
                        Q(associated_participant_id__in=participant_ids)
                    )
                
                filter_conditions |= type_filter
                
                # 2. Additionally include signals from legacy participants (regardless of type)
                if legacy_participant_ids:
                    legacy_filter = Q(
                        Q(participant_id__in=legacy_participant_ids) | 
                        Q(associated_participant_id__in=legacy_participant_ids)
                    )
                    filter_conditions |= legacy_filter
                
                # 3. No additional filters needed
                
                # Apply the combined filter
                accessible_signals = accessible_signals.filter(filter_conditions)
            elif legacy_participant_ids:
                # No participant types specified, just use legacy participants
                accessible_signals = accessible_signals.filter(
                    Q(participant_id__in=legacy_participant_ids) | 
                    Q(associated_participant_id__in=legacy_participant_ids)
                )
    elif applied_filters and applied_filters.participants:
        # Legacy participant filtering for backward compatibility
        participant_ids = [int(p_id) for p_id in applied_filters.participants]
        accessible_signals = accessible_signals.filter(
            Q(participant_id__in=participant_ids) | 
            Q(associated_participant_id__in=participant_ids)
        )
    
    # Privacy filtering removed - all participants are accessible
    # No additional filtering needed
    
    # Only return cards that have at least one accessible signal
    return queryset.filter(Exists(accessible_signals))


@strawberry.type
class Query:
    @strawberry_django.field
    @monitor_query_performance("optimized_signal_cards")
    def signal_cards(
        self,
        info,
        filters: Optional[SignalCardFilters] = None,
        pagination: Optional[PaginationInput] = None,
        card_type: Optional[CardType] = CardType.ALL,
        sort_by: Optional[SortBy] = SortBy.LATEST_SIGNAL_DATE,
        sort_order: Optional[SortOrder] = SortOrder.DESC,
        folder_id: Optional[strawberry.ID] = None,
        folder_key: Optional[str] = None,
        include_signals: Optional[bool] = False,
        absolute_image_url: Optional[bool] = True,
        include_assigned_members: Optional[bool] = False
    ) -> SignalCardConnection:
        """
        Получает пагинированные карточки сигналов с расширенной фильтрацией и оптимизацией.
        
        Этот резолвер включает:
        - Анализ сложности запроса для предотвращения дорогих операций
        - Паттерн DataLoader для эффективной пакетной загрузки
        - Умное кэширование и предзагрузку
        - Мониторинг производительности
        - Кэширование результатов на уровне запроса
        - Поддержку фильтрации по папкам (параметр folder_key)
        """
        validate_query_complexity(info, raise_on_invalid=True)
        
        complexity_analysis = analyze_query_complexity(info)
        query_complexity_score = complexity_analysis.get('complexity', 0)
        if query_complexity_score > 20:
            query_complexity = 'comprehensive'
        elif query_complexity_score > 10:
            query_complexity = 'heavy'
        elif query_complexity_score > 5:
            query_complexity = 'moderate'
        else:
            query_complexity = 'lightweight'
        
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        from .query_caching import get_cache_manager
        cache_manager = get_cache_manager()
        filters_dict = _serialize_filters_for_cache(filters)
        
        pagination_dict = None
        if pagination:
            pagination_dict = {
                'page': pagination.page,
                'page_size': pagination.page_size
            }
        
        # Define the computation function
        def compute_signal_cards():
            """Вычисляет результат карточек сигналов без кэширования."""
            from .enhanced_prefetching import create_optimized_queryset
            base_queryset = _get_optimized_signal_cards_queryset(user, include_signals)
            queryset = create_optimized_queryset(base_queryset, info, user)
            folder_ordering_applied = False
            if folder_key:
                from profile.models import UserFolder, FolderCard
                from django.db.models import Case, When, Value, IntegerField
                
                try:
                    # Handle folder_key logic like REST API
                    if folder_key == 'default':
                        # Get user's default folder
                        folder = UserFolder.objects.filter(user=user, is_default=True).first()
                        if not folder:
                            # Return empty queryset if default folder not found
                            queryset = queryset.none()
                        else:
                            # Get folder cards with ordering by FolderCard.id in reverse order
                            folder_cards = FolderCard.objects.filter(
                                folder=folder
                            ).select_related('signal_card').order_by('-id')
                            
                            folder_card_ids = [fc.signal_card_id for fc in folder_cards]
                            queryset = queryset.filter(id__in=folder_card_ids)
                            
                            # Apply folder ordering - same as REST API
                            if folder_card_ids:
                                case_clauses = [When(id=card_id, then=Value(i)) for i, card_id in enumerate(folder_card_ids)]
                                queryset = queryset.annotate(
                                    folder_position=Case(*case_clauses, default=Value(len(folder_card_ids)), output_field=IntegerField())
                                ).order_by('folder_position')
                                folder_ordering_applied = True
                    elif folder_key == 'remote':
                        # Handle remote cards (deleted cards) - matches REST API type=remote behavior
                        deleted_cards = DeletedCard.objects.filter(
                            user=user
                        ).values_list('signal_card_id', flat=True)
                        queryset = queryset.filter(id__in=deleted_cards)
                        # Note: Don't apply folder ordering for remote cards, use default sorting
                    else:
                        # Handle specific folder ID
                        try:
                            folder_id_int = int(folder_key)
                            folder = UserFolder.objects.filter(id=folder_id_int, user=user).first()
                            if not folder:
                                # Return empty queryset if folder not found
                                queryset = queryset.none()
                            else:
                                # Get folder cards with ordering by FolderCard.id in reverse order
                                folder_cards = FolderCard.objects.filter(
                                    folder=folder
                                ).select_related('signal_card').order_by('-id')
                                
                                folder_card_ids = [fc.signal_card_id for fc in folder_cards]
                                queryset = queryset.filter(id__in=folder_card_ids)
                                
                                # Apply folder ordering - same as REST API
                                if folder_card_ids:
                                    case_clauses = [When(id=card_id, then=Value(i)) for i, card_id in enumerate(folder_card_ids)]
                                    queryset = queryset.annotate(
                                        folder_position=Case(*case_clauses, default=Value(len(folder_card_ids)), output_field=IntegerField())
                                    ).order_by('folder_position')
                                    folder_ordering_applied = True
                        except (ValueError, TypeError):
                            # Invalid folder ID - return empty queryset
                            queryset = queryset.none()
                            
                except Exception:
                    # On any error, return empty queryset
                    queryset = queryset.none()
            
            # Apply card type filters (only if folder_key is not specified)
            elif card_type == CardType.SAVED:
                if folder_id:
                    try:
                        folder_cards = FolderCard.objects.filter(
                            folder_id=int(folder_id),
                            folder__user=user
                        ).values_list('signal_card_id', flat=True)
                        queryset = queryset.filter(id__in=folder_cards)
                    except (ValueError, TypeError):
                        queryset = queryset.none()
                else:
                    # Get default saved cards
                    folder_cards = FolderCard.objects.filter(
                        folder__user=user,
                        folder__is_default=True
                    ).values_list('signal_card_id', flat=True)
                    queryset = queryset.filter(id__in=folder_cards)
                
            elif card_type == CardType.NOTES:
                noted_cards = UserNote.objects.filter(
                    user=user
                ).values_list('signal_card_id', flat=True)
                queryset = queryset.filter(id__in=noted_cards)
                
            elif card_type == CardType.DELETED:
                deleted_cards = DeletedCard.objects.filter(
                    user=user
                ).values_list('signal_card_id', flat=True)
                queryset = queryset.filter(id__in=deleted_cards)
                
            elif card_type == CardType.WORTH_FOLLOWING:
                queryset = queryset.filter(stage='worth_following')
                
            else:  # CardType.ALL
                # Exclude deleted cards for ALL view
                deleted_cards = DeletedCard.objects.filter(
                    user=user,
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.exclude(Exists(deleted_cards))
                # Include worth_following signals in ALL view per user request
            
            # Apply filters and track search relevance (only if folder ordering not applied)
            if not folder_ordering_applied:
                queryset, has_search_relevance = _apply_optimized_filters(queryset, filters, user)
            else:
                # For folder queries, still apply filters but don't change sorting
                queryset, has_search_relevance = _apply_optimized_filters(queryset, filters, user)
                has_search_relevance = False  # Override to maintain folder ordering
            
            # ESSENTIAL: Filter out cards with no signals at all (needed for participants to show)
            # But use simpler logic than the original _filter_cards_with_accessible_signals
            if include_signals:
                from signals.models import Signal
                has_signals = Signal.objects.filter(
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.filter(Exists(has_signals))
            
            # Apply sorting with database optimization (only if folder ordering not applied)
            if not folder_ordering_applied:
                # latest_signal_date annotation is already applied in base queryset
                
                # Apply sorting with search relevance priority
                if has_search_relevance:
                    # For search queries: sort by relevance first, then by latest signal date for same relevance
                    queryset = queryset.distinct().order_by('-search_relevance', '-latest_signal_date', '-created_at')
                else:
                    # For non-search queries: use standard sorting
                    if sort_by == SortBy.LATEST_SIGNAL_DATE:
                        # CRITICAL FIX: Use NULLS LAST for latest_signal_date to ensure LinkedIn signals appear at top
                        from django.db.models import F
                        queryset = queryset.distinct().order_by(
                            F('latest_signal_date').desc(nulls_last=True), 
                            '-created_at'
                        )
                    elif sort_by == SortBy.CREATED_AT:
                        order_field = 'created_at'
                    elif sort_by == SortBy.NAME:
                        order_field = 'name'
                    elif sort_by == SortBy.UPDATED_AT:
                        order_field = 'updated_at'
                    else:
                        # Default to latest_signal_date with NULLS LAST
                        from django.db.models import F
                        queryset = queryset.distinct().order_by(
                            F('latest_signal_date').desc(nulls_last=True), 
                            '-created_at'
                        )
                    # Skip the generic order_by below for latest_signal_date cases
                    if sort_by not in [SortBy.LATEST_SIGNAL_DATE, None]:
                        if sort_order == SortOrder.DESC:
                            order_field = f'-{order_field}'
                            
                        queryset = queryset.distinct().order_by(order_field, '-created_at')
            
            # Handle pagination
            page = pagination.page if pagination else 1
            page_size = pagination.page_size if pagination else 20
            page_size = min(page_size, 100)  # Cap at 100 for performance
            
            # Use Django's Paginator for efficient pagination
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            # The QueryOptimizer will automatically:
            # 1. Add select_related() for foreign keys
            # 2. Add prefetch_related() for many-to-many relations  
            # 3. Use only() for requested fields
            # 4. Handle annotations for computed fields
            
            return SignalCardConnection(
                nodes=list(page_obj),
                total_count=paginator.count,
                has_next_page=page_obj.has_next(),
                has_previous_page=page_obj.has_previous(),
                current_page=page,
                total_pages=paginator.num_pages
            )

        if query_complexity in ['comprehensive', 'heavy']:
            # Use cache manager's get_or_compute_signal_cards method
            return cache_manager.get_or_compute_signal_cards(
                compute_func=compute_signal_cards,
                user_id=user.id if user else None,
                filters=filters_dict,
                pagination=pagination_dict,
                card_type=card_type.value if card_type else 'all',
                sort_by=sort_by.value if sort_by else 'latest_signal_date',
                sort_order=sort_order.value if sort_order else 'desc',
                include_signals=include_signals,
                query_complexity=query_complexity,
                display_preference='ALL',
                folder_id=str(folder_id) if folder_id else None,
                folder_key=folder_key
            )
        else:
            return compute_signal_cards()

    @strawberry_django.field
    @monitor_query_performance("optimized_user_feed")
    def user_feed(
        self,
        info,
        pagination: Optional[PaginationInput] = None,
        filters: Optional[SignalCardFilters] = None,
        include_signals: Optional[bool] = False,
        absolute_image_url: Optional[bool] = True,
        bypass_personal_filters: Optional[bool] = True
    ) -> SignalCardConnection:
        """
        Получает комплексную ленту пользователя, показывающую ВСЕ доступные карточки сигналов с расширенной оптимизацией.
        
        Этот резолвер включает:
        - Показывает все доступные карточки сигналов (не только от отслеживаемых участников)
        - Фильтрацию приватности для уважения доступа пользователя к приватным участникам
        - Опциональный обход персональных фильтров ленты для показа ВСЕХ доступных сигналов
        - Анализ сложности запроса для предотвращения дорогих операций
        - Паттерн DataLoader для эффективной пакетной загрузки
        - Пользовательское кэширование и предзагрузку
        - Мониторинг производительности
        - Оптимизацию комплексной ленты с пакетной загрузкой
        
        Args:
            bypass_personal_filters: Если True (по умолчанию), игнорирует сохраненные предпочтения ленты пользователя
                                    (категории, стадии) и показывает ВСЕ доступные карточки сигналов.
                                    Установите False для применения персональных фильтров ленты.
        """
        validate_query_complexity(info, raise_on_invalid=True)
        
        complexity_analysis = analyze_query_complexity(info)
        query_complexity_score = complexity_analysis.get('complexity', 0)
        if query_complexity_score > 20:
            query_complexity = 'comprehensive'
        elif query_complexity_score > 10:
            query_complexity = 'heavy'
        elif query_complexity_score > 5:
            query_complexity = 'moderate'
        else:
            query_complexity = 'lightweight'
        
        # Initialize DataLoader manager for this request
        dataloader_manager = get_dataloader_manager(info)
        
        # Enhanced prefetching strategy for N+1 prevention
        enhanced_prefetch = [
            'categories',
            'team_members',
            'signals__participant',
            'signals__associated_participant',
            'signals__signal_type',
        ]
        
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            # Return empty result for unauthenticated users
            return SignalCardConnection(
                nodes=[],
                total_count=0,
                has_next_page=False,
                has_previous_page=False,
                current_page=1,
                total_pages=0
            )
        
        # Import cache managers
        from .comprehensive_query_caching import get_comprehensive_cache_manager
        from .enhanced_bulk_loading import optimize_signal_cards_for_comprehensive_feed
        
        cache_manager = get_comprehensive_cache_manager()
        
        # Prepare cache parameters
        filters_dict = _serialize_filters_for_cache(filters)
        
        pagination_dict = None
        if pagination:
            pagination_dict = {
                'page': pagination.page,
                'page_size': pagination.page_size
            }

        def compute_user_feed():
            """Вычисляет ленту пользователя со всеми оптимизациями."""
            try:
                user_feed = UserFeed.objects.get(user=user)
            except UserFeed.DoesNotExist:
                # Create default UserFeed configuration to show all content
                user_feed = UserFeed.objects.create(user=user)

            # CRITICAL FIX: Use the same base queryset as signal_cards for consistent sorting
            # This ensures latest_signal_date annotation is applied early and consistently
            queryset = _get_optimized_signal_cards_queryset(user, include_signals=True)
            
            # Apply enhanced prefetching optimization like signal_cards
            from .enhanced_prefetching import create_optimized_queryset
            queryset = create_optimized_queryset(queryset, info, user)
            
            # Exclude deleted cards efficiently
            deleted_cards = DeletedCard.objects.filter(
                user=user,
                signal_card=OuterRef('pk')
            )
            queryset = queryset.exclude(Exists(deleted_cards))
            
            # Apply personal feed filters only if not bypassed
            if not bypass_personal_filters:
                # Apply feed category filters
                if user_feed.categories.exists():
                    category_ids = list(user_feed.categories.values_list('id', flat=True))
                    category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
                    queryset = queryset.filter(category_filter)
                
                # Apply feed stage and round filters
                if user_feed.stages or user_feed.round_statuses:
                    stage_round_filter = Q()
                    if user_feed.stages:
                        stage_round_filter |= Q(stage__in=user_feed.stages)
                    if user_feed.round_statuses:
                        stage_round_filter |= Q(round_status__in=user_feed.round_statuses)
                    queryset = queryset.filter(stage_round_filter)
                
            
            # NOTE: latest_signal_date annotation is already applied in _get_optimized_signal_cards_queryset
            # No need to re-apply it here to avoid conflicts
            
            # Apply additional filters from GraphQL query and track search relevance
            queryset, has_search_relevance = _apply_optimized_filters(queryset, filters, user)
            
            # CRITICAL: Filter out cards with no accessible signals to prevent empty signals arrays
            # Note: This function now preserves participant filtering from _apply_optimized_filters
            if include_signals:
                queryset = _filter_cards_with_accessible_signals(queryset, user, filters)
            
            # Apply sorting with search relevance priority
            if has_search_relevance:
                # For search queries: sort by relevance first, then by latest signal date for same relevance
                # Use NULLS LAST to ensure cards with signals appear before cards without signals
                queryset = queryset.distinct().order_by('-search_relevance', '-latest_signal_date', '-created_at')
            else:
                # For non-search queries: standard sorting by latest signal date
                # CRITICAL FIX: Use NULLS LAST to ensure LinkedIn signals (and all signals) appear at the top
                from django.db.models import F
                queryset = queryset.distinct().order_by(
                    F('latest_signal_date').desc(nulls_last=True), 
                    '-created_at'
                )
            
            # Handle pagination
            page = pagination.page if pagination else 1
            page_size = pagination.page_size if pagination else 20
            page_size = min(page_size, 100)  # Cap at 100 for performance
            
            # Use Django's Paginator for efficient pagination
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            # Get the signal cards for this page
            signal_cards = list(page_obj)
            
            # CRITICAL OPTIMIZATION: Apply comprehensive feed optimization for bulk loading
            if include_signals and signal_cards:

                signal_cards = optimize_signal_cards_for_comprehensive_feed(
                    signal_cards=signal_cards,
                    user=user,
                    info=info
                )
            
            return SignalCardConnection(
                nodes=signal_cards,
                total_count=paginator.count,
                has_next_page=page_obj.has_next(),
                has_previous_page=page_obj.has_previous(),
                current_page=page,
                total_pages=paginator.num_pages
            )

        # Use comprehensive caching for expensive queries
        if query_complexity in ['comprehensive', 'heavy'] or include_signals:
            return cache_manager.get_or_compute_comprehensive_feed(
                compute_func=compute_user_feed,
                user_id=user.id,
                filters=filters_dict,
                pagination=pagination_dict,
                include_signals=include_signals,
                query_complexity=query_complexity,
                display_preference='ALL',
                bypass_personal_filters=bypass_personal_filters
            )
        else:
            # For lightweight queries, compute directly without caching overhead

            return compute_user_feed()

    @strawberry_django.field
    def signal_card(
        self,
        info,
        id: Optional[strawberry.ID] = None,
        slug: Optional[str] = None,
        uuid: Optional[str] = None,
        include_signals: Optional[bool] = True,
        absolute_image_url: Optional[bool] = True
    ) -> Optional[SignalCardType]:
        """Получает одну карточку сигнала по ID, slug или UUID с оптимизацией."""
        queryset = SignalCard.objects.annotate(
            latest_signal_date=Max('signals__created_at'),
            oldest_signal_date=Min('signals__created_at')
        )
        
        if include_signals:
            queryset = queryset.prefetch_related(
                'signals__participant',
                'signals__associated_participant',
                'signals__signal_type',
            )
        queryset = queryset.prefetch_related(
            'categories',
            'team_members'
        )
        
        try:
            if id:
                return queryset.get(id=id)
            elif slug:
                return queryset.get(slug=slug)
            elif uuid:
                return queryset.get(uuid=uuid)
            else:
                return None
        except SignalCard.DoesNotExist:
            return None

    @strawberry_django.field
    @monitor_query_performance("group_assignments")
    def group_assignments(
        self,
        info,
        pagination: Optional[PaginationInput] = None,
        statuses: Optional[List[AssignmentStatus]] = None,
        filter_type: Optional[AssignmentFilterType] = AssignmentFilterType.MY_ASSIGNMENTS,
        include_signals: Optional[bool] = False,
        include_assigned_members: Optional[bool] = False
    ) -> GroupAssignedCardConnection:
        """
        Get group assignments (cards assigned to user's group) with filtering
        
        Args:
            pagination: Pagination parameters
            statuses: Filter by assignment statuses (REVIEW=Review, REACHING_OUT=Reaching out, CONNECTED=Connected, NOT_A_FIT=Not a Fit)
            filter_type: 
                - MY_ASSIGNMENTS: Only cards where the current user is specifically assigned
                - ALL: All cards assigned to the user's group
            include_signals: Whether to include signals in the response
            include_assigned_members: Whether to include assigned members list with metadata
        """
        
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return GroupAssignedCardConnection(
                nodes=[],
                total_count=0,
                has_next_page=False,
                has_previous_page=False,
                current_page=1,
                total_pages=0
            )
        
        # Get user's group
        if not hasattr(user, 'group') or not user.group:
            return GroupAssignedCardConnection(
                nodes=[],
                total_count=0,
                has_next_page=False,
                has_previous_page=False,
                current_page=1,
                total_pages=0
            )
        
        user_group = user.group
        
        # Store flag in request context for field resolver
        request = info.context.get("request")
        if request:
            if not hasattr(request, '_graphql_flags'):
                request._graphql_flags = {}
            request._graphql_flags['include_assigned_members'] = include_assigned_members or False
        
        # Build queryset for group assignments
        prefetch_related = [
            'signal_card__categories',
            'signal_card__team_members'
        ]
        
        # Prefetch assigned members if flag is set
        if include_assigned_members:
            from profile.models import GroupCardMemberAssignment
            prefetch_related.append(
                Prefetch(
                    'member_assignments',
                    queryset=GroupCardMemberAssignment.objects.select_related('user', 'assigned_by'),
                    to_attr='prefetched_assignments'
                )
            )
        
        queryset = GroupAssignedCard.objects.filter(group=user_group).select_related(
            'group',
            'signal_card'
        ).prefetch_related(*prefetch_related)
        
        # Apply status filter
        if statuses:
            status_values = [status.value for status in statuses]
            queryset = queryset.filter(status__in=status_values)
        
        # Apply filter_type
        if filter_type == AssignmentFilterType.MY_ASSIGNMENTS:
            # Filter only cards where the current user is specifically assigned
            from profile.models import GroupCardMemberAssignment
            from django.db.models import Exists, OuterRef
            user_assignments = GroupCardMemberAssignment.objects.filter(
                group_assigned_card=OuterRef('pk'),
                user=user
            )
            queryset = queryset.filter(Exists(user_assignments))
        elif filter_type == AssignmentFilterType.ALL:
            # Show all cards assigned to the group (already filtered by group above)
            pass
        
        # Order by created_at descending (newest first)
        queryset = queryset.order_by('-created_at')
        
        # Handle pagination
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        page_size = min(page_size, 100)  # Cap at 100 for performance
        
        # Use Django's Paginator for efficient pagination
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # Convert to GraphQL types
        assignments = list(page_obj)
        
        return GroupAssignedCardConnection(
            nodes=assignments,
            total_count=paginator.count,
            has_next_page=page_obj.has_next(),
            has_previous_page=page_obj.has_previous(),
            current_page=page,
            total_pages=paginator.num_pages
        )

    @strawberry_django.field
    def categories(self, info) -> List[CategoryType]:
        """Получает категории на основе предпочтений пользователя - родительские для ALL/WEB2, подкатегории для WEB3."""
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        # Показываем все родительские категории (всегда ALL)
        categories_query = Category.objects.filter(parent_category_id__isnull=True)
        
        return categories_query.order_by('name')


    @strawberry_django.field
    @monitor_query_performance("participants_relay_paginated")
    def participants(
        self, 
        info, 
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
        search: Optional[str] = None,
        funds_only: Optional[bool] = None,
        types: Optional[List[str]] = None,
        is_saved: Optional[bool] = None,
        sort_by_activity: bool = strawberry.argument(name="sortByActivity", description="Sort participants by monthly signals count")
    ) -> ParticipantRelayConnection:
        """Получает пагинированных участников с Relay-стиль курсорной пагинацией, умным поиском и корректной обработкой приватности."""
        import base64
        
        request = info.context.get("request") if info.context else None
        user = request.user if request and request.user.is_authenticated else None
        

        queryset = Participant.objects.all()
        
        if user:
            queryset = queryset.prefetch_related(
                Prefetch('saved_by_users', 
                        queryset=SavedParticipant.objects.filter(user=user),
                        to_attr='user_saved_status')
            )
        
        if funds_only is True:
            queryset = queryset.filter(associated_with=F('id'))
        elif funds_only is False:
            queryset = queryset.exclude(associated_with=F('id'))
        
        if types:
            queryset = queryset.filter(type__in=types)
        
        # Web filtering removed - all participants are accessible (always ALL)
        
        if sort_by_activity:
            queryset = queryset.order_by('-monthly_signals_count', 'name')
        
        # Privacy filtering removed - all participants are accessible
        
        # Apply saved filter if specified
        if is_saved is not None and user:
            if is_saved:
                # Filter for saved participants only
                saved_participant_ids = set(SavedParticipant.objects.filter(
                    user=user
                ).values_list('participant_id', flat=True))
                queryset = queryset.filter(id__in=saved_participant_ids)
            else:
                # Filter for unsaved participants only
                saved_participant_ids = set(SavedParticipant.objects.filter(
                    user=user
                ).values_list('participant_id', flat=True))
                queryset = queryset.exclude(id__in=saved_participant_ids)
        
        if search and search.strip():
            search_term = search.strip()
            
            exact_name_search = Q(name__icontains=search_term) | Q(additional_name__icontains=search_term)
            broader_search = Q(about__icontains=search_term) | Q(slug__icontains=search_term)
            
            exact_matches = list(queryset.filter(exact_name_search).select_related('associated_with'))
            
            broader_matches = []
            if len(exact_matches) < 10:
                broader_matches = list(queryset.filter(broader_search).exclude(
                    id__in=[p.id for p in exact_matches]
                ).select_related('associated_with'))
            
            all_matches = exact_matches + broader_matches
            
            result_participants = []
            seen_participant_ids = set()
            
            for participant in all_matches:
                if participant.id in seen_participant_ids:
                    continue
                seen_participant_ids.add(participant.id)
                
                has_strong_name_match = any(search_term.lower() in field.lower() 
                                          for field in [participant.name, participant.additional_name or ''] 
                                          if field)
                
                should_include = False
                
                if has_strong_name_match:
                    should_include = True
                
                elif any(search_term.lower() in field.lower() 
                        for field in [participant.about or '', participant.slug or ''] 
                        if field):
                    should_include = True
                
                if should_include and funds_only is not None:
                    is_fund = participant.associated_with_id == participant.id
                    if funds_only and not is_fund:
                        should_include = False
                    elif not funds_only and is_fund:
                        should_include = False
                
                # Check is_saved filter
                if should_include and is_saved is not None and user:
                    participant_is_saved = SavedParticipant.objects.filter(
                        user=user,
                        participant=participant
                    ).exists()
                    if participant_is_saved != is_saved:
                        should_include = False
                
                if should_include:
                    result_participants.append(participant)
                    
                    if (participant.associated_with_id and 
                        participant.associated_with and 
                        participant.associated_with_id != participant.id and
                        has_strong_name_match and
                        funds_only is not False):
                        
                        fund = participant.associated_with
                        
                        fund_passes_filters = True
                        
                        # Privacy filtering removed
                        
                        if types and fund.type not in types:
                            fund_passes_filters = False
                        
                        # Check is_saved filter for fund
                        if is_saved is not None and user:
                            fund_is_saved = SavedParticipant.objects.filter(
                                user=user,
                                participant=fund
                            ).exists()
                            if fund_is_saved != is_saved:
                                fund_passes_filters = False
                        
                        if fund_passes_filters and fund.id not in seen_participant_ids:
                            result_participants.append(fund)
                            seen_participant_ids.add(fund.id)
            
            unique_participants = []
            final_seen_ids = set()
            for p in result_participants:
                if p.id not in final_seen_ids:
                    unique_participants.append(p)
                    final_seen_ids.add(p.id)
            
            def sort_key(p):
                
                is_fund = p.associated_with_id == p.id
                high_value_types = {'investor', 'angel', 'founder', 'fund', 'accelerator', 'scout'}
                
                if funds_only is not False and is_fund:
                    priority = 0
                elif p.type in high_value_types:
                    priority = 1
                else:
                    priority = 2
                
                return (priority, p.name.lower())
            
            unique_participants.sort(key=sort_key)
            participants_list = unique_participants
            
            stats_queryset = participants_list
            
            # Handle pagination for search results
            total_count = len(participants_list)
            page_size = first or last or 20
            page_size = min(page_size, 100)
            
            def parse_cursor(cursor):
                try:
                    decoded = base64.b64decode(cursor).decode('utf-8')
                    return int(decoded.split(':')[1])
                except (ValueError, IndexError, AttributeError):
                    return 0
            
            start_offset = 0
            if after:
                start_offset = parse_cursor(after) + 1
            elif before:
                end_offset = parse_cursor(before)
                start_offset = max(0, end_offset - page_size)
            
            if last:
                if before:
                    end_offset = min(total_count, parse_cursor(before))
                else:
                    end_offset = total_count
                start_offset = max(0, end_offset - last)
                end_offset = min(total_count, start_offset + last)
            else:
                end_offset = min(total_count, start_offset + page_size)
            
            page_data = participants_list[start_offset:end_offset]
            
            edges = []
            for i, participant in enumerate(page_data):
                cursor_index = start_offset + i
                cursor = base64.b64encode(f"participant:{cursor_index}".encode('utf-8')).decode('utf-8')
                
                edges.append(ParticipantEdge(
                    node=participant,
                    cursor=cursor
                ))
            
            has_previous_page = start_offset > 0
            has_next_page = end_offset < total_count
            
            start_cursor = edges[0].cursor if edges else None
            end_cursor = edges[-1].cursor if edges else None
            
            page_info = PageInfo(
                has_next_page=has_next_page,
                has_previous_page=has_previous_page,
                start_cursor=start_cursor,
                end_cursor=end_cursor
            )
        
        else:
            if not sort_by_activity:
                queryset = queryset.distinct().order_by('name')
            
            stats_queryset = queryset
            
            participants_list = list(queryset)
            
            if sort_by_activity:
                participants_list.sort(key=lambda p: (-(p.monthly_signals_count or 0), p.name.lower()))
            
            total_count = len(participants_list)
            
            page_size = first or last or 20
            page_size = min(page_size, 100)
            
            def parse_cursor(cursor):
                try:
                    decoded = base64.b64decode(cursor).decode('utf-8')
                    return int(decoded.split(':')[1])
                except (ValueError, IndexError, AttributeError):
                    return 0
            
            start_offset = 0
            if after:
                start_offset = parse_cursor(after) + 1
            elif before:
                end_offset = parse_cursor(before)
                start_offset = max(0, end_offset - page_size)
            
            if last:
                if before:
                    end_offset = min(total_count, parse_cursor(before))
                else:
                    end_offset = total_count
                start_offset = max(0, end_offset - last)
                end_offset = min(total_count, start_offset + last)
            else:
                end_offset = min(total_count, start_offset + page_size)
            
            page_data = participants_list[start_offset:end_offset]
            
            edges = []
            for i, participant in enumerate(page_data):
                cursor_index = start_offset + i
                cursor = base64.b64encode(f"participant:{cursor_index}".encode('utf-8')).decode('utf-8')
                
                edges.append(ParticipantEdge(
                    node=participant,
                    cursor=cursor
                ))
            
            has_previous_page = start_offset > 0
            has_next_page = end_offset < total_count
            
            start_cursor = edges[0].cursor if edges else None
            end_cursor = edges[-1].cursor if edges else None
            
            page_info = PageInfo(
                has_next_page=has_next_page,
                has_previous_page=has_previous_page,
                start_cursor=start_cursor,
                end_cursor=end_cursor
            )
            
        return ParticipantRelayConnection(
            edges=edges,
            page_info=page_info,
            total_count=total_count,
            category_stats=[]
        )

    @strawberry_django.field
    def stages(self, info) -> List[StageFilter]:
        """Получает все доступные стадии."""
        return [
            StageFilter(
                slug=stage_tuple[0],
                name=stage_tuple[1],
                stats=FilterStats(count=0, active=False)
            )
            for stage_tuple in STAGES
        ]

    @strawberry_django.field
    def roundStatuses(self, info) -> List[RoundFilter]:
        """Получает все доступные статусы раундов."""
        return [
            RoundFilter(
                slug=round_tuple[0],
                name=round_tuple[1],
                stats=FilterStats(count=0, active=False)
            )
            for round_tuple in ROUNDS
        ]

    # Location functionality removed - methods deleted

    @strawberry_django.field
    @monitor_query_performance("saved_filters")
    def saved_filters(
        self,
        info,
        pagination: Optional[PaginationInput] = None,
        include_recent_counts: Optional[bool] = False
    ) -> SavedFilterConnection:
        """
        Get all saved filters for the authenticated user with pagination.
        
        Args:
            pagination: Pagination parameters
            include_recent_counts: If True, compute recentProjectsCount for each filter. 
                                 If False, skip expensive computation for better performance.
        """
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return SavedFilterConnection(
                nodes=[],
                total_count=0,
                has_next_page=False,
                has_previous_page=False,
                current_page=1,
                total_pages=0
            )
        
        # Store the flag in the request context so the field resolver can access it
        if not hasattr(request, '_graphql_flags'):
            request._graphql_flags = {}
        request._graphql_flags['include_recent_counts'] = include_recent_counts or False
        
        # Get saved filters for the user, ordered by default status and updated date
        queryset = SavedFilterModel.objects.filter(user=user).prefetch_related(
            'categories', 'participants'
        )
        
        # Показываем все сохраненные фильтры (всегда ALL)
        
        # Apply ordering after filtering
        queryset = queryset.order_by('-is_default', '-updated_at', 'name')
        
        # Handle pagination
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        page_size = min(page_size, 100)  # Cap at 100 for performance
        
        # Use Django's Paginator for efficient pagination
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return SavedFilterConnection(
            nodes=list(page_obj.object_list),
            total_count=paginator.count,
            has_next_page=page_obj.has_next(),
            has_previous_page=page_obj.has_previous(),
            current_page=page,
            total_pages=paginator.num_pages
        )
    
    @strawberry_django.field
    @monitor_query_performance("default_saved_filter")
    def default_saved_filter(self, info) -> Optional[SavedFilter]:
        """Get the user's default saved filter."""
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return None
        
        try:
            default_filter_query = SavedFilterModel.objects.prefetch_related(
                'categories', 'participants'
            ).filter(user=user, is_default=True)
            
            # Показываем все фильтры (всегда ALL)
            return default_filter_query.first()
        except SavedFilterModel.DoesNotExist:
            return None
    
    @strawberry_django.field
    @monitor_query_performance("saved_filters_summary")
    def saved_filters_summary(self, info) -> SavedFilterListResult:
        """
        Get a summary of all saved filters for the authenticated user.
        """
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return SavedFilterListResult(
                saved_filters=[],
                total_count=0,
                default_filter=None
            )
        
        # Get all saved filters for the user
        saved_filters = SavedFilterModel.objects.filter(user=user).prefetch_related(
            'categories', 'participants'
        )
        
        # Apply ordering
        saved_filters = saved_filters.order_by('-is_default', '-updated_at', 'name')
        
        # Get default filter separately for easy access
        default_filter = None
        try:
            default_filter_query = SavedFilterModel.objects.prefetch_related(
                'categories', 'participants'
            ).filter(user=user, is_default=True)
            
            default_filter = default_filter_query.first()
        except SavedFilterModel.DoesNotExist:
            pass
        
        return SavedFilterListResult(
            saved_filters=list(saved_filters),
            total_count=saved_filters.count(),
            default_filter=default_filter
        )