from django.db.models import Count, Case, When, Max, Value, F, Q, IntegerField
from django.utils import timezone
from datetime import timedelta
from profile.models import User
from django.shortcuts import get_object_or_404
from django.db import models

def get_user_by_id(user_id):
    user = get_object_or_404(User, pk=user_id)
    return user

def get_date_range(date_filter):
    now = timezone.now()
    if date_filter == 'today':
        return now - timedelta(days=1), now
    elif date_filter == 'this_week' or date_filter == 'last_week':
        return now - timedelta(days=7), now
    elif date_filter == 'this_month':
        return now - timedelta(days=31), now
    return None, None


def apply_signal_count_filters(signal_cards, min_sig, max_sig, unique=True):
    """
    Применяет фильтры по количеству сигналов.
    Параметр unique больше не используется, так как всегда True.
    """
    if min_sig > 1 or max_sig:
        # Всегда считаем сигналы с уникальными родительскими участниками
        signal_cards = signal_cards.annotate(
            signal_count=Count(
                Case(
                    When(
                        signals__participant__associated_with__isnull=False,
                        then='signals__participant__associated_with'
                    ),
                    default='signals__participant',
                ),
                distinct=True
            )
        )
        
        if min_sig > 1:
            signal_cards = signal_cards.filter(signal_count__gte=min_sig)
        
        if max_sig:
            signal_cards = signal_cards.filter(signal_count__lte=max_sig)
    
    return signal_cards


def apply_search_query_filters(signal_cards, search_query):
    """
    Применяет фильтры и аннотации для поискового запроса и рассчитывает релевантность результатов.
    
    Args:
        signal_cards: QuerySet объектов SignalCard или список объектов SignalCard
        search_query: Строка поискового запроса
        
    Returns:
        Кортеж (отфильтрованный QuerySet или список, флаг использования сортировки по релевантности)
    """
    # Если поисковый запрос пустой, возвращаем исходный QuerySet без изменений
    if not search_query or search_query.strip() == '':
        return signal_cards, False
    
    # Check if signal_cards is a list and not a QuerySet
    if isinstance(signal_cards, list):
        # Filter the list manually
        filtered_cards = [
            card for card in signal_cards 
            if (search_query.lower() in card.name.lower() or 
                (card.description and search_query.lower() in card.description.lower()))
        ]
        # No relevance sorting for lists
        return filtered_cards, False
        
    # Фильтруем сигнальные карточки только по названию и описанию
    filtered_cards = signal_cards.filter(
        Q(name__icontains=search_query) | 
        Q(description__icontains=search_query)
    ).distinct()
    
    # Аннотируем только отфильтрованные карточки для расчета релевантности
    filtered_cards = filtered_cards.annotate(
        search_relevance=Case(
            # Приоритет точных совпадений в имени
            When(name__iexact=search_query, then=Value(100)),
            # Приоритет частичных совпадений в имени
            When(name__icontains=search_query, then=Value(75)),
            # Наименьший приоритет для описания
            When(description__icontains=search_query, then=Value(25)),
            default=Value(0),
            output_field=IntegerField()
        )
    )
    
    return filtered_cards, True