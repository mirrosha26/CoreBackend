from signals.models import SignalCard, STAGES, ROUNDS, Participant, Signal, TeamMember
from profile.models import UserFolder, FolderCard, UserNote
from django.conf import settings
from django.utils import timezone as django_timezone
from datetime import timezone as dt_timezone, timedelta
from django.db.models import Q, Count
from .utils import build_absolute_image_url


def get_saved_participant_ids(user):
    """Получает множество ID сохраненных участников пользователя"""
    return set(Participant.objects.filter(
        saved_by_users__user=user
    ).distinct().values_list('id', flat=True))


def normalize_social_key(name):
    """
    Нормализует название социальной сети в стандартный ключ (slug).
    
    Args:
        name: Название социальной сети (например, "Twitter", "LinkedIn")
        
    Returns:
        str: Нормализованный ключ (например, "twitter", "linkedin")
    """
    import re
    # Приводим к lowercase и заменяем пробелы/спецсимволы на подчеркивания
    key = re.sub(r'[^\w\s-]', '', name.lower())
    key = re.sub(r'[-\s]+', '_', key)
    # Убираем лишние подчеркивания
    key = key.strip('_')
    return key


def extract_social_links(more_data):
    """
    Извлекает социальные ссылки из поля more модели SignalCard.
    Исключает reference_url и другие служебные поля.
    
    Args:
        more_data: JSON данные из поля more
        
    Returns:
        list: Список словарей с социальными ссылками в формате:
              [{"key": "twitter", "name": "Twitter", "url": "..."}, ...]
    """
    social_links = []
    
    if not more_data or not isinstance(more_data, list):
        return social_links
    
    # Поля, которые не должны попадать в social_links
    excluded_fields = {'reference_url', 'project_url', 'url'}
    
    # Ищем блок с социальными сетями
    for block in more_data:
        if block.get("name") == "Social" and block.get("type") == "links" and isinstance(block.get("value"), dict):
            # Преобразуем словарь социальных сетей в список
            for name, url in block.get("value", {}).items():
                # Пропускаем служебные поля (case-insensitive проверка)
                name_lower = name.lower()
                if url and name_lower not in excluded_fields:
                    social_links.append({
                        "key": normalize_social_key(name),
                        "name": name,
                        "url": url
                    })
    
    return social_links


def clean_more_data(more_data):
    """
    Удаляет извлеченные социальные ссылки из поля more.
    Если после удаления что-то осталось, возвращает это, иначе None.
    
    Args:
        more_data: JSON данные из поля more
        
    Returns:
        dict/list/None: Очищенные данные или None, если ничего не осталось
    """
    if not more_data:
        return None
    
    # Если more_data - это не список, возвращаем как есть (может быть объект)
    if not isinstance(more_data, list):
        return more_data
    
    # Удаляем блок с социальными ссылками
    cleaned_blocks = []
    for block in more_data:
        # Пропускаем блок с социальными ссылками
        if block.get("name") == "Social" and block.get("type") == "links":
            continue
        cleaned_blocks.append(block)
    
    # Если после очистки ничего не осталось, возвращаем None
    if not cleaned_blocks:
        return None
    
    # Если остался один блок, можно вернуть его напрямую, но лучше вернуть список
    return cleaned_blocks


def get_liked_cards_ids(user, signal_cards_ids=None):
    """Получает множество ID карточек, которые пользователь добавил в избранное"""
    default_folder = UserFolder.objects.filter(user=user, is_default=True).only('id').first()

    if not default_folder:
        return set()
        
    query = FolderCard.objects.filter(folder=default_folder)
    
    if signal_cards_ids:
        query = query.filter(signal_card_id__in=signal_cards_ids)
    
    return set(query.values_list('signal_card_id', flat=True))


def get_cards_with_notes_ids(user, signal_cards_ids=None):
    """Получает множество ID карточек, к которым пользователь добавил заметки"""
    if not signal_cards_ids:
        return set()
        
    return set(UserNote.objects.filter(
        user=user, 
        signal_card_id__in=signal_cards_ids
    ).values_list('signal_card_id', flat=True))


def get_card_folders(user, signal_card_id):
    """
    Получает список названий папок, в которых находится карточка.
    
    Args:
        user: Пользователь
        signal_card_id: ID карточки
    
    Returns:
        list: Список названий папок
    """
    folders = UserFolder.objects.filter(
        user=user,
        folder_cards__signal_card_id=signal_card_id
    ).values_list('name', flat=True)
    
    return list(folders)


def get_cards_trending_status(signal_cards_ids, user):
    """
    Вычисляет trending статус для списка карточек одним запросом.
    Trending = минимум 5 уникальных associated_participants за последнюю неделю.
    
    Args:
        signal_cards_ids: Список ID карточек
        user: Пользователь для фильтрации приватных участников
    
    Returns:
        set: Множество ID карточек, которые являются trending
    """
    if not signal_cards_ids:
        return set()
    
    from django.utils import timezone
    
    # Дата неделю назад
    one_week_ago = timezone.now() - timedelta(days=7)
    
    # ParticipantRequest больше не используется
    requested_participant_ids = set()
    
    # Получаем карточки с количеством уникальных associated_participants за последнюю неделю
    # С учетом приватности
    trending_cards = (
        Signal.objects.filter(
            signal_card_id__in=signal_cards_ids,
            created_at__gte=one_week_ago
        )
        .filter(
            # Должен быть хотя бы один участник
            # linkedin_data и source_signal_card удалены из модели Signal
            Q(participant__isnull=False) | 
            Q(associated_participant__isnull=False)
        )
        .filter(
            # Privacy filtering removed - all participants are accessible
            Q(
                participant__isnull=False
            ) | Q(
                associated_participant__isnull=False
            )
        )
        .values('signal_card_id', 'associated_participant_id')
        .distinct()
        .values('signal_card_id')
        .annotate(unique_participants=Count('associated_participant_id', distinct=True))
        .filter(unique_participants__gte=5)
        .values_list('signal_card_id', flat=True)
    )
    
    return set(trending_cards)


def get_cards_folders_mapping(user, signal_cards_ids):
    """
    Получает словарь {card_id: [folder_objects]} для всех карточек.
    Оптимизированная версия для массовой загрузки.
    
    Args:
        user: Пользователь
        signal_cards_ids: Список ID карточек
    
    Returns:
        dict: Словарь {card_id: [{"id": int, "name": str}]}
    """
    if not signal_cards_ids:
        return {}
    
    # Получаем все папки пользователя с карточками
    folder_cards = FolderCard.objects.filter(
        folder__user=user,
        signal_card_id__in=signal_cards_ids
    ).select_related('folder', 'signal_card')
    
    # Формируем словарь
    cards_folders = {}
    for folder_card in folder_cards:
        card_id = folder_card.signal_card_id
        folder = folder_card.folder
        
        if card_id not in cards_folders:
            cards_folders[card_id] = []
        
        # Добавляем объект папки (проверяем, чтобы не было дубликатов)
        folder_obj = {"id": folder.id, "name": folder.name}
        if folder_obj not in cards_folders[card_id]:
            cards_folders[card_id].append(folder_obj)
    
    return cards_folders


def get_cards_participants_mapping(signal_cards_ids, saved_participant_ids, limit=5):
    """
    Получает участников для всех карточек одним запросом (bulk loading).
    Оптимизированная версия для предотвращения N+1 запросов.
    
    Args:
        signal_cards_ids: Список ID карточек
        saved_participant_ids: Set ID сохраненных участников
        limit: Максимальное количество участников на карточку
    
    Returns:
        dict: {card_id: {"participants_list": [...], "participants_more_count": int, "participants_has_more": bool}}
    """
    if not signal_cards_ids:
        return {}
    
    # Более эффективный подход: получаем связи напрямую через Signal
    # Это избегает множественных JOIN'ов и prefetch'ов
    signals_data = Signal.objects.filter(
        signal_card_id__in=signal_cards_ids,
        associated_participant__isnull=False
    ).select_related('associated_participant').values(
        'signal_card_id',
        'associated_participant_id',
        'associated_participant__name',
        'associated_participant__image',
    )
    
    # Убираем дубликаты в Python (более надежно, чем distinct на уровне БД)
    seen_pairs = set()
    unique_signals_data = []
    for signal_data in signals_data:
        pair = (signal_data['signal_card_id'], signal_data['associated_participant_id'])
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            unique_signals_data.append(signal_data)
    
    signals_data = unique_signals_data
    
    # Группируем участников по карточкам
    cards_participants = {}
    for signal_data in signals_data:
        card_id = signal_data['signal_card_id']
        participant_id = signal_data['associated_participant_id']
        
        # Privacy filtering removed
        
        if card_id not in cards_participants:
            cards_participants[card_id] = []
        
        cards_participants[card_id].append({
            'id': participant_id,
            'name': signal_data['associated_participant__name'],
            'image': signal_data['associated_participant__image'],
        })
    
    # Загружаем все изображения участников одним запросом (bulk loading)
    all_participant_ids = set()
    for participants_list in cards_participants.values():
        for p in participants_list:
            all_participant_ids.add(p['id'])
    
    # Получаем все участники с изображениями одним запросом
    participants_with_images = {
        p.id: p
        for p in Participant.objects.filter(id__in=all_participant_ids).only('id', 'image')
    }
    
    # Сериализуем участников для каждой карточки
    result = {}
    for card_id in signal_cards_ids:
        participants_list = cards_participants.get(card_id, [])
        
        # Ограничиваем количество
        visible_participants = participants_list[:limit]
        more_count = len(participants_list) - len(visible_participants)
        
        # Формируем финальный список с изображениями
        serialized_participants = []
        for participant_data in visible_participants:
            participant_id = participant_data['id']
            participant_obj = participants_with_images.get(participant_id)
            image_url = build_absolute_image_url(participant_obj, True) if participant_obj else None
            
            serialized_participants.append({
                "name": participant_data['name'],
                "image": image_url,
                "is_saved": participant_id in saved_participant_ids,
            })
        
        result[card_id] = {
            "participants_list": serialized_participants,
            "participants_more_count": more_count,
            "participants_has_more": more_count > 0
        }
    
    return result


def serialize_associated_participants(signal_card, saved_participant_ids, limit=5):
    """
    Сериализует уникальных ассоциированных участников карточки с учетом приватности.
    
    DEPRECATED: Используйте get_cards_participants_mapping для bulk loading.
    Оставлено для обратной совместимости.
    
    Args:
        signal_card: Объект SignalCard
        saved_participant_ids: Set ID сохраненных участников
        limit: Максимальное количество участников для сериализации
    
    Returns:
        dict: Словарь с сериализованными участниками и их общим количеством
    """
    # Получаем всех уникальных ассоциированных участников
    # Используем prefetch для оптимизации
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


def serialize_card_previews(signal_cards, user, include_user_data=False):
    """
    Сериализует список карточек для клиентского API.
    Оптимизированная версия с bulk loading для предотвращения N+1 запросов.
    
    Args:
        signal_cards: QuerySet или список объектов SignalCard (уже должен быть prefetch'нут)
        user: Пользователь для которого сериализуются данные
        include_user_data: Если True, добавляет пользовательские данные (is_liked, has_note, note, folders)
    
    Returns:
        list: Список словарей с данными карточек
    """
    # Преобразуем в список для работы с данными
    # Важно: делаем это после всех prefetch'ов, но до итерации
    if hasattr(signal_cards, '__iter__'):
        signal_cards_list = list(signal_cards)
    else:
        signal_cards_list = []
    
    # Получаем ID карточек для оптимизации запросов
    signal_cards_ids = [card.id for card in signal_cards_list]
    
    if not signal_cards_ids:
        return []
    
    # Вычисляем trending статус для всех карточек одним запросом
    trending_cards_ids = get_cards_trending_status(signal_cards_ids, user)
    
    # Пользовательские данные загружаем ТОЛЬКО если include_user_data=True
    liked_cards_ids = set()
    cards_with_notes_ids = set()
    cards_folders_mapping = {}
    user_notes = {}
    
    if include_user_data:
        liked_cards_ids = get_liked_cards_ids(user, signal_cards_ids)
        cards_with_notes_ids = get_cards_with_notes_ids(user, signal_cards_ids)
        cards_folders_mapping = get_cards_folders_mapping(user, signal_cards_ids)
        
        # Получаем заметки пользователя для всех карточек (без id, как в fullcard.json)
        user_notes = {
            note.signal_card_id: {
                "text": note.note_text,
                "created_at": format_datetime_utc(note.created_at),
                "updated_at": format_datetime_utc(note.updated_at),
            }
            for note in UserNote.objects.filter(
                user=user,
                signal_card_id__in=signal_cards_ids
            )
        }
    
    # Базовый URL для публичных ссылок
    base_url = getattr(settings, 'BASE_URL', 'https://app.theveck.com')
    if not base_url.endswith('/'):
        base_url += '/'
    
    serialized_cards = []
    
    for card in signal_cards_list:
        card_data = {
            # Обязательные поля (всегда присутствуют)
            "id": card.id,
            "slug": card.slug,
            "name": card.name,
            "public_url": f"{base_url}public/{card.slug}",
            "interactions_count": getattr(card, 'interactions_count', 0),
            "trending": card.id in trending_cards_ids,
            
            # Опциональные поля (показываем с null если отсутствуют)
            "description": card.description if card.description else None,
            "image": build_absolute_image_url(card, absolute_image_url=True, base_url=base_url),  # Абсолютный URL
            # Используем reference_url если есть, иначе url (они обычно одинаковые)
            "url": card.reference_url if card.reference_url else (card.url if card.url else None),
            
            # Статусы (всегда присутствуют, но могут быть Unknown)
            # Примечание: stage и round - это choices (CharField), у них нет id, только slug
            "stage": {
                "name": dict(STAGES).get(card.stage, 'Unknown'),
                "slug": card.stage if card.stage else None
            },
            "round": {
                "name": dict(ROUNDS).get(card.round_status, 'Unknown'),
                "slug": card.round_status if card.round_status else None
            },
            
            # Категории (всегда массив, может быть пустым)
            # Используем только slug (id скрыт, т.к. не используется для фильтрации)
            "categories": [
                {"name": cat.name, "slug": cat.slug}
                for cat in card.categories.all()
            ],
            
            # Location fields were removed from SignalCard model
            
            # Даты (упрощенный ISO формат без миллисекунд, в UTC)
            "created_at": format_datetime_utc(card.created_at),
            "updated_at": format_datetime_utc(card.updated_at),
            "last_round": card.last_round.strftime("%Y-%m-%d") if card.last_round else None,
            "last_interaction_at": format_datetime_utc(getattr(card, 'latest_signal_date', None)),
            "first_interaction_at": format_datetime_utc(getattr(card, 'oldest_signal_date', None)),
            
            # Социальные ссылки (всегда массив, может быть пустым)
            "social_links": extract_social_links(card.more),
        }
        
        # Пользовательские данные (только если include_user_data=True)
        if include_user_data:
            card_data["user_data"] = {
                "is_liked": card.id in liked_cards_ids,
                "has_note": card.id in cards_with_notes_ids,
                "note": user_notes.get(card.id) if card.id in cards_with_notes_ids else None,
                "folders": cards_folders_mapping.get(card.id, [])
            }
        
        serialized_cards.append(card_data)
    
    return serialized_cards


def format_datetime_utc(dt):
    """
    Форматирует datetime в UTC ISO формат без миллисекунд.
    
    Args:
        dt: datetime объект (может быть naive или aware)
    
    Returns:
        str: Отформатированная дата в формате "2025-11-13T16:24:32Z" или None
    """
    if not dt:
        return None
    if django_timezone.is_naive(dt):
        dt = django_timezone.make_aware(dt)
    return dt.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def serialize_team_members(signal_card):
    """
    Сериализует участников команды (TeamMember) для карточки.
    
    Args:
        signal_card: Объект SignalCard (должен быть prefetch'нут с team_members)
    
    Returns:
        list: Список словарей с данными участников команды
    """
    team_members = []
    for member in signal_card.team_members.all():
        team_members.append({
            "name": member.name,
            "headline": member.headline,
            "email": member.email,
            "image": build_absolute_image_url(member, True),
            "links": {
                "site": member.site,
                "crunchbase": member.crunchbase,
                "twitter": member.twitter,
                "linkedin": member.linkedin,
                "instagram": member.instagram,
                "github": member.github,
                "producthunt": member.producthunt,
            }
        })
    return team_members


def serialize_user_note(user, signal_card_id):
    """
    Получает заметку пользователя для карточки.
    
    Args:
        user: Пользователь
        signal_card_id: ID карточки
    
    Returns:
        dict: Словарь с данными заметки или None
    """
    try:
        note = UserNote.objects.get(user=user, signal_card_id=signal_card_id)
        return {
            "id": note.id,
            "text": note.note_text,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
    except UserNote.DoesNotExist:
        return None


def serialize_card_detail(signal_card, user, include_user_data=False):
    """
    Сериализует детальную информацию о карточке для клиентского API.
    Использует формат списка карточек с расширенными полями.
    Всегда включает до 20 последних взаимодействий (покрывает 95% проектов).
    Для получения всех взаимодействий используйте отдельный эндпоинт /cards/<slug>/interactions/
    
    Args:
        signal_card: Объект SignalCard (должен быть prefetch'нут со всеми связанными данными)
        user: Пользователь для которого сериализуются данные
        include_user_data: Если True, добавляет пользовательские данные (is_liked, has_note, note, folders) (по умолчанию False)
    
    Returns:
        dict: Словарь с детальными данными карточки
    """
    # Вычисляем trending статус
    trending_cards_ids = get_cards_trending_status([signal_card.id], user)
    
    # Пользовательские данные загружаем ТОЛЬКО если include_user_data=True
    liked_cards_ids = set()
    cards_with_notes_ids = set()
    cards_folders_mapping = {}
    user_note_data = None
    
    if include_user_data:
        liked_cards_ids = get_liked_cards_ids(user, [signal_card.id])
        cards_with_notes_ids = get_cards_with_notes_ids(user, [signal_card.id])
        cards_folders_mapping = get_cards_folders_mapping(user, [signal_card.id])
        
        # Получаем заметку пользователя (без id, как в fullcard.json)
        if signal_card.id in cards_with_notes_ids:
            try:
                note = UserNote.objects.get(user=user, signal_card_id=signal_card.id)
                user_note_data = {
                    "text": note.note_text,
                    "created_at": format_datetime_utc(note.created_at),
                    "updated_at": format_datetime_utc(note.updated_at),
                }
            except UserNote.DoesNotExist:
                pass
    
    # Базовый URL для публичных ссылок
    base_url = getattr(settings, 'BASE_URL', 'https://app.theveck.com')
    if not base_url.endswith('/'):
        base_url += '/'
    
    # Формируем данные карточки в формате списка с расширенными полями
    card_data = {
        # Базовые поля (как в списке)
        "id": signal_card.id,
        "slug": signal_card.slug,
        "name": signal_card.name,
        "public_url": f"{base_url}public/{signal_card.slug}",
        "interactions_count": Signal.objects.filter(signal_card=signal_card).count(),
        "trending": signal_card.id in trending_cards_ids,
        
        # Опциональные поля
        "description": signal_card.description if signal_card.description else None,
        "image": build_absolute_image_url(signal_card, absolute_image_url=True, base_url=base_url),
        "url": signal_card.reference_url if signal_card.reference_url else (signal_card.url if signal_card.url else None),
        
        # Статусы (как в списке)
        # Примечание: stage и round - это choices (CharField), у них нет id, только slug
        "stage": {
            "name": dict(STAGES).get(signal_card.stage, 'Unknown'),
            "slug": signal_card.stage if signal_card.stage else None
        },
        "round": {
            "name": dict(ROUNDS).get(signal_card.round_status, 'Unknown'),
            "slug": signal_card.round_status if signal_card.round_status else None
        },
        
        # Категории (как в списке)
        # Используем только slug (id скрыт, т.к. не используется для фильтрации)
        "categories": [
            {"name": cat.name, "slug": cat.slug}
            for cat in signal_card.categories.all()
        ],
        
        # Location fields were removed from SignalCard model
        
        # Даты
        "created_at": format_datetime_utc(signal_card.created_at),
        "updated_at": format_datetime_utc(signal_card.updated_at),
        "last_round": signal_card.last_round.strftime("%Y-%m-%d") if signal_card.last_round else None,
        "last_interaction_at": format_datetime_utc(getattr(signal_card, 'latest_signal_date', None)),
        "first_interaction_at": format_datetime_utc(getattr(signal_card, 'oldest_signal_date', None)),
        
        # Социальные ссылки
        "social_links": extract_social_links(signal_card.more),
    }
    
    # Пользовательские данные (только если include_user_data=True)
    if include_user_data:
        card_data["user_data"] = {
            "is_liked": signal_card.id in liked_cards_ids,
            "has_note": signal_card.id in cards_with_notes_ids,
            "note": user_note_data,
            "folders": cards_folders_mapping.get(signal_card.id, []),
        }
    
    # Расширенные поля (только в детальном ответе)
    card_data["team_members"] = serialize_team_members(signal_card)
    card_data["more"] = clean_more_data(signal_card.more)
    
    # Взаимодействия (всегда показываем до 20 последних - покрывает 95% проектов)
    # Для получения всех взаимодействий используйте отдельный эндпоинт /cards/<slug>/interactions/
    card_data["interactions"] = []
    card_data["has_more_interactions"] = False
    
    # Получаем общее количество взаимодействий
    total_interactions = Signal.objects.filter(signal_card=signal_card).count()
    
    # Всегда показываем до 20 последних взаимодействий (от самых свежих к самым давним)
    signals = Signal.objects.filter(
        signal_card=signal_card
    ).select_related(
        'participant',
        'associated_participant'
    ).order_by('-created_at')[:20]
    
    # Сериализуем взаимодействия
    card_data["interactions"] = [
        {
            "id": signal.id,
            "created_at": format_datetime_utc(signal.created_at),
            "participant": {
                "name": signal.participant.name,
                "slug": signal.participant.slug,
                "type": signal.participant.type,
            } if signal.participant else None,
            "associated_participant": {
                "name": signal.associated_participant.name,
                "slug": signal.associated_participant.slug,
                "type": signal.associated_participant.type,
            } if signal.associated_participant else None,
        }
        for signal in signals
    ]
    
    # Устанавливаем флаг, если есть еще взаимодействия
    card_data["has_more_interactions"] = total_interactions > 20
    
    return card_data


def serialize_interactions(signals):
    """
    Сериализует список взаимодействий (сигналов).
    
    Args:
        signals: QuerySet или список объектов Signal
    
    Returns:
        list: Список словарей с данными взаимодействий
    """
    return [
        {
            "id": signal.id,
            "created_at": format_datetime_utc(signal.created_at),
            "participant": {
                "name": signal.participant.name,
                "slug": signal.participant.slug,
                "type": signal.participant.type,
            } if signal.participant else None,
            "associated_participant": {
                "name": signal.associated_participant.name,
                "slug": signal.associated_participant.slug,
                "type": signal.associated_participant.type,
            } if signal.associated_participant else None,
        }
        for signal in signals
    ]

