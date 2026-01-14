from django.db.models import Max, Min
from signals.models import  Signal, STAGES, ROUNDS
from frontend_api.serializers.cards.signals import serialize_signals
from frontend_api.serializers.utils import build_absolute_image_url
from .base import (
    extract_social_links,
)


def serialize_public_card_preview(signal_card):
    """
    Сериализатор preview карточки - основная информация.
    
    Args:
        signal_card: Объект SignalCard
    
    Returns:
        dict: Основная информация о карточке для preview
    """
    # Преобразуем категории в список, чтобы избежать проблем с QuerySet
    try:
        categories_list = [
            {"id": cat.id, "name": cat.name, "slug": cat.slug}
            for cat in signal_card.categories.all()
        ]
    except Exception:
        categories_list = []
    
    card_data = {
        # Основная информация
        "id": signal_card.id,
        "slug": signal_card.slug,
        "uuid": str(signal_card.uuid) if signal_card.uuid else None,
        "name": signal_card.name,
        "description": signal_card.description,
        "image": build_absolute_image_url(signal_card, True),
        "url": signal_card.url,
        
        # Даты
        "created_date": signal_card.created_at.strftime("%Y-%m-%d") if signal_card.created_at else None,
        "last_round": signal_card.last_round.strftime("%Y-%m-%d") if signal_card.last_round else None,
        
        # Статусы и этапы
        "stage_info": {
            "name": dict(STAGES).get(signal_card.stage, 'Unknown'),
            "slug": signal_card.stage
        },
        "round_status_info": {
            "key": signal_card.round_status,
            "name": dict(ROUNDS).get(signal_card.round_status, 'Unknown')
        },
        
        # Местоположение и социальные сети
        "location": signal_card.location if signal_card.location else "",
        "social_links": extract_social_links(signal_card.more) if signal_card.more else [],
        
        # Категории
        "categories_list": categories_list
    }
    
    return card_data


def serialize_public_card_detail(signal_card, include_signals=True, signals_limit=None):
    """
    Сериализатор detail карточки - детальная информация.
    
    Args:
        signal_card: Объект SignalCard
        include_signals: Включать ли сигналы в ответ
        signals_limit: Ограничение количества сигналов (None = без ограничений)
    
    Returns:
        dict: Детальная информация о карточке
    """
    # Вычисляем даты вручную
    try:
        signals_dates = signal_card.signals.aggregate(
            latest_date=Max('created_at'),
            oldest_date=Min('created_at')
        )
    except Exception:
        signals_dates = {'latest_date': None, 'oldest_date': None}
    
    # Get categories
    try:
        categories_data = [
            {"id": cat.id, "name": cat.name, "slug": cat.slug}
            for cat in signal_card.categories.all()
        ]
    except Exception:
        categories_data = []
    
    detail_data = {
        # Основная информация
        "id": signal_card.id,
        "slug": signal_card.slug,
        "uuid": str(signal_card.uuid) if signal_card.uuid else None,
        "name": signal_card.name,
        "description": signal_card.description,
        "image": build_absolute_image_url(signal_card, True),
        "url": signal_card.url,
        
        # Даты
        "created_date": signal_card.created_at.strftime("%Y-%m-%d") if signal_card.created_at else None,
        "latest_signal_date": signals_dates['latest_date'].strftime("%Y-%m-%d") if signals_dates['latest_date'] else None,
        "discovered_at": signals_dates['oldest_date'].strftime("%Y-%m-%d") if signals_dates['oldest_date'] else None,
        "last_round": signal_card.last_round.strftime("%Y-%m-%d") if signal_card.last_round else None,
        
        # Статусы и этапы
        "stage_info": {
            "name": dict(STAGES).get(signal_card.stage, 'Unknown'),
            "slug": signal_card.stage
        },
        "round_status_info": {
            "key": signal_card.round_status,
            "name": dict(ROUNDS).get(signal_card.round_status, 'Unknown')
        },
        
        # Местоположение и социальные сети
        "location": signal_card.location if signal_card.location else "",
        "social_links": extract_social_links(signal_card.more) if signal_card.more else [],
        
        # Категории
        "categories": categories_data,
    }
    
    # Добавляем сигналы, если требуется
    if include_signals:
        saved_participant_ids = set()
        signals = serialize_signals(
            signals=Signal.with_related.filter(signal_card=signal_card),
            saved_participant_ids=saved_participant_ids,
            absolute_image_url=True,
            limit=signals_limit
        )
        detail_data['signals'] = signals
    
    return detail_data
