from django.db.models import Q
from signals.models import SignalCard, STAGES, ROUNDS, Participant
from profile.models import UserFolder, FolderCard, UserNote, TicketForCard
from frontend_api.serializers.utils import build_absolute_image_url
from .base import (
    extract_social_links,
    get_saved_participant_ids,
    get_liked_cards_ids,
    get_cards_with_notes_ids,
    serialize_associated_participants
)

def serialize_previews(signal_cards, user):
    # Предварительно получаем все необходимые данные одним запросом
    saved_participant_ids = get_saved_participant_ids(user)
    
    # Получаем ID карточек для оптимизации запросов
    signal_cards_ids = [card.id for card in signal_cards] if signal_cards else []
    
    liked_cards_ids = get_liked_cards_ids(user, signal_cards_ids)
    cards_with_notes_ids = get_cards_with_notes_ids(user, signal_cards_ids)
    
    # Предварительно загружаем связанные данные для всех карточек
    # Используем prefetch_related для уменьшения количества запросов
    if signal_cards and hasattr(signal_cards, 'prefetch_related'):
        signal_cards = signal_cards.prefetch_related(
            'categories', 
            'signals__associated_participant'  # Предзагружаем ассоциированных участников
        )
    
    serialized_cards = []
    
    for card in signal_cards:
        card_data = {
            "id": card.id,
            "slug": card.slug,
            "uuid": card.uuid,
            "name": card.name,
            "image": build_absolute_image_url(card, True),
            "is_liked": card.id in liked_cards_ids,
            "has_note": card.id in cards_with_notes_ids,
            "stage_info": {
                "name": dict(STAGES).get(card.stage, 'Unknown'),
                "slug": card.stage
            },
            "round_status_info": {
                "key": card.round_status,
                "name": dict(ROUNDS).get(card.round_status, 'Unknown')
            },
            "created_date": card.created_at.strftime("%Y-%m-%d") if card.created_at else None,
            "latest_date": getattr(card, 'latest_signal_date', None),
            "location": card.get_location_data() if hasattr(card, 'get_location_data') and card.location else {
                "formatted": card.location if card.location else None,
                "city": None,
                "state": None, 
                "country": None,
                "region": None,
                "type": None
            },
            "last_round": card.last_round.strftime("%Y-%m-%d") if card.last_round else None,
            "url": card.url if card.url else None,  # Добавляем URL проекта
            "social_links": extract_social_links(card.more)  # Добавляем социальные сети
        }
        
        if card_data["latest_date"]:
            card_data["latest_date"] = card_data["latest_date"].strftime("%Y-%m-%d")
        
        # Добавляем описание (полное или None)
        card_data["description"] = card.description if card.description else None
        
        # Добавляем все категории (пустой список, если их нет)
        categories = [
            {"id": cat.id, "name": cat.name, "slug": cat.slug}
            for cat in card.categories.all()
        ]
        card_data["categories_list"] = categories
        
        # Используем новый сериализатор для ассоциированных участников
        associated_data = serialize_associated_participants(card, saved_participant_ids, limit=4) 
        
        card_data["participants_list"] = associated_data["participants_list"]
        card_data["participants_more_count"] = associated_data["participants_more_count"]
        card_data["participants_has_more"] = associated_data["participants_has_more"]
        
        serialized_cards.append(card_data)
    
    return serialized_cards