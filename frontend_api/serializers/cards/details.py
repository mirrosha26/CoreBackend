from django.db.models import Max, Min, Q
from signals.models import SignalCard, Signal, STAGES, ROUNDS
from profile.models import FolderCard, DeletedCard, UserNote, UserFolder, SavedParticipant, TicketForCard
from frontend_api.serializers.cards.participant import serialize_participant, serialize_linkedin_data
from frontend_api.serializers.cards.signals import serialize_signals
from frontend_api.serializers.utils import build_absolute_image_url


def serialize_card_detail(signal_card, user, include_signals=True):
    signal_card = SignalCard.with_related.filter(
        id=signal_card.id
    ).annotate(
        oldest_signal_date=Min('signals__created_at'),
        latest_signal_date=Max('signals__created_at')
    ).first()
    
    # Получаем ID сохраненных участников для пользователя
    saved_participant_ids = set(SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True))
    
    # Получение информации о статусе карточки для пользователя
    
    is_liked = FolderCard.objects.filter(
        folder__user=user,
        folder__is_default=True,
        signal_card=signal_card
    ).exists()
    
    is_deleted = DeletedCard.objects.filter(
        user=user,
        signal_card=signal_card
    ).exists()
    
    # Проверяем, создал ли пользователь тикет для этой карточки
    has_ticket = TicketForCard.objects.filter(
        user=user,
        signal_card=signal_card
    ).exists()
    
    # Упрощенная обработка заметки - возвращаем None или текст заметки
    user_note_text = None
    has_note = False
    try:
        note = UserNote.objects.get(user=user, signal_card=signal_card)
        user_note_text = note.note_text
        has_note = True
    except UserNote.DoesNotExist:
        pass
    
    # Получение папок, в которых находится карточка
    folders = []
    # Получаем все папки пользователя
    all_user_folders = UserFolder.objects.filter(user=user)
    
    # Получаем ID папок, в которых находится карточка
    folders_with_card_ids = set(UserFolder.objects.filter(
        user=user,
        folder_cards__signal_card=signal_card
    ).values_list('id', flat=True))
    
    for folder in all_user_folders:
        folders.append({
            'id': folder.id,
            'name': folder.name,
            'is_default': folder.is_default,
            'has_card': folder.id in folders_with_card_ids
        })
    
    # Базовые данные карточки в формате, аналогичном serialize_signal_cards
    card_data = {
        "has_ticket": has_ticket,
        "is_liked": is_liked,
        "latest_signal_date": signal_card.latest_signal_date.strftime("%Y-%m-%d") if signal_card.latest_signal_date else None,
        "discovered_at": signal_card.oldest_signal_date.strftime("%Y-%m-%d") if hasattr(signal_card, 'oldest_signal_date') and signal_card.oldest_signal_date else None,
    }
    
    # Получение и сериализация участников и LinkedIn данных
    participants = []
    
    # Получаем участников, связанных с сигналами этой карточки
    for signal in signal_card.signals.all():
        # Handle participant signals only (LinkedIn data is handled in signals section)
        if signal.participant:  # Проверяем, что у сигнала есть участник
            participant_data = serialize_participant(
                participant=signal.participant,
                signal=signal,
                absolute_image_url=True,
                saved_participant_ids=saved_participant_ids
            )
            participants.append(participant_data)
        
        # Также проверяем associated_participant, если он есть
        if hasattr(signal, 'associated_participant') and signal.associated_participant:
            participant_data = serialize_participant(
                participant=signal.associated_participant,
                signal=signal,
                absolute_image_url=True,
                saved_participant_ids=saved_participant_ids
            )
            participants.append(participant_data)
    
    # Добавляем участников в данные карточки
    card_data['participants'] = participants
    
    # Добавляем сигналы, если требуется (включая LinkedIn данные)
    if include_signals:
        signals = serialize_signals(
            signals=Signal.with_related.filter(signal_card=signal_card),
            saved_participant_ids=saved_participant_ids,
            absolute_image_url=True
        )
        card_data['signals'] = signals
    
    # Добавление пользовательской информации
    card_data['user_data'] = {
        'note_text': user_note_text,
        'folders': folders
    }
    
    return card_data

