from signals.models import Participant, Source
from profile.models import SavedParticipant
from .utils import build_absolute_image_url


def serialize_source(source):
    """
    Сериализует источник (Source) для клиентского API.
    
    Args:
        source: Объект Source
    
    Returns:
        dict: Словарь с данными источника
    """
    return {
        "slug": source.slug,
        "type": source.source_type.slug if source.source_type else None,
        "link": source.get_profile_link() if hasattr(source, 'get_profile_link') else None,
    }


def serialize_participant(participant, user=None, include_sources=False, include_user_data=False):
    """
    Сериализует участника для клиентского API.
    
    Args:
        participant: Объект Participant (должен быть prefetch'нут с associated_with и sources если нужно)
        user: Пользователь для проверки доступа к приватным участникам
        include_sources: Если True, включает список источников (только для детального ответа)
        include_user_data: Если True, включает пользовательские данные (is_saved)
    
    Returns:
        dict: Словарь с данными участника
    """
    # Проверяем, сохранен ли участник пользователем (только если include_user_data=True)
    is_saved = False
    if include_user_data and user and user.is_authenticated:
        is_saved = SavedParticipant.objects.filter(
            user=user,
            participant=participant
        ).exists()
    
    # Проверяем, ассоциирован ли участник сам с собой (fund case)
    is_self_associated = participant.associated_with == participant if participant.associated_with else False
    
    result = {
        "slug": participant.slug,
        "name": participant.name,
        "alt_name": participant.additional_name if participant.additional_name else None,
        "image": build_absolute_image_url(participant, True),
        "type": participant.type,
        "about": participant.about if participant.about else None,
        "monthly_signals": participant.monthly_signals_count,
        "associated_with": {
            "slug": participant.associated_with.slug,
            "name": participant.associated_with.name,
        } if participant.associated_with else None,
        "self_associated": is_self_associated,
    }
    
    # Добавляем is_saved только если include_user_data=True
    if include_user_data:
        result["is_saved"] = is_saved
    
    # Добавляем источники только если запрошено (для детального ответа)
    if include_sources:
        # Получаем все активные источники (не заблокированные и существующие)
        sources = Source.objects.filter(
            participant=participant,
            blocked=False,
            nonexistent=False
        ).select_related('source_type')
        
        result["sources"] = [serialize_source(source) for source in sources]
    
    return result


def serialize_participants(participants, user=None, include_user_data=False):
    """
    Сериализует список участников для клиентского API.
    
    Args:
        participants: QuerySet или список объектов Participant (должен быть prefetch'нут с associated_with)
        user: Пользователь для проверки доступа к приватным участникам
        include_user_data: Если True, включает пользовательские данные (is_saved)
    
    Returns:
        list: Список словарей с данными участников
    """
    return [serialize_participant(p, user, include_sources=False, include_user_data=include_user_data) for p in participants]

