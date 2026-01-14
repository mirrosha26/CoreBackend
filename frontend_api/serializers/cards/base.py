from signals.models import Participant
from profile.models import UserFolder, FolderCard, UserNote
from frontend_api.serializers.utils import build_absolute_image_url


def get_saved_participant_ids(user):
    return set(Participant.objects.filter(
        saved_by_users__user=user
    ).distinct().values_list('id', flat=True))

def extract_social_links(more_data):
    """
    Извлекает социальные ссылки из поля more модели SignalCard.
    
    Args:
        more_data: JSON данные из поля more
        
    Returns:
        list: Список словарей с социальными ссылками
    """
    social_links = []
    
    if not more_data or not isinstance(more_data, list):
        return social_links
    
    # Ищем блок с социальными сетями
    for block in more_data:
        if block.get("name") == "Social" and block.get("type") == "links" and isinstance(block.get("value"), dict):
            # Преобразуем словарь социальных сетей в список
            for name, url in block.get("value", {}).items():
                if url:  # Добавляем только непустые URL
                    social_links.append({
                        "name": name,
                        "url": url
                    })
    
    return social_links


def get_liked_cards_ids(user, signal_cards_ids=None):
    default_folder = UserFolder.objects.filter(user=user, is_default=True).only('id').first()

    if not default_folder:
        return set()
        
    query = FolderCard.objects.filter(folder=default_folder)
    
    if signal_cards_ids:
        query = query.filter(signal_card_id__in=signal_cards_ids)
    
    return set(query.values_list('signal_card_id', flat=True))


def get_cards_with_notes_ids(user, signal_cards_ids=None):
    if not signal_cards_ids:
        return set()
        
    return set(UserNote.objects.filter(
        user=user, 
        signal_card_id__in=signal_cards_ids
    ).values_list('signal_card_id', flat=True))

def serialize_associated_participants(signal_card, saved_participant_ids, limit=5):
    """
    Сериализует уникальных ассоциированных участников карточки с учетом приватности.
    
    Args:
        signal_card: Объект SignalCard
        saved_participant_ids: Set ID сохраненных участников
        limit: Максимальное количество участников для сериализации
    
    Returns:
        dict: Словарь с сериализованными участниками и их общим количеством
    """
    # Получаем всех уникальных ассоциированных участников
    associated_participants = Participant.objects.filter(
        associated_signals__signal_card=signal_card
    ).distinct()
    
    # Общее количество уникальных ассоциированных участников
    total_count = associated_participants.count()
    
    # Фильтруем участников, которые видны пользователю
    visible_participants = []
    for participant in associated_participants:
        if participant:
            visible_participants.append(participant)
    
    # Ограничиваем количество видимых участников для сериализации
    serialized_participants = []
    count = 0
    
    for participant in visible_participants:
        if count >= limit:
            break
            
        participant_data = {
            "name": participant.name,
            "image": build_absolute_image_url(participant, True),
            "is_saved": participant.id in saved_participant_ids,
        }
        serialized_participants.append(participant_data)
        count += 1
    
    # Количество видимых участников
    visible_count = len(visible_participants)
    
    # Количество дополнительных участников, которые не вошли в лимит
    more_count = visible_count - min(visible_count, limit)
    
    return {
        "participants_list": serialized_participants,
        "participants_more_count": more_count,
        "participants_has_more": more_count > 0
    }
