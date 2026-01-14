"""
Реализация DataLoader для батчинга GraphQL запросов для уменьшения проблем N+1.

Модуль предоставляет эффективную пакетную загрузку связанных данных
для минимизации запросов к БД и улучшения производительности GraphQL.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Count, Max

from profile.models import UserNote, FolderCard, DeletedCard, SavedParticipant
from signals.models import SignalCard, Signal, Category, Participant

logger = logging.getLogger(__name__)


@dataclass
class BatchLoadResult:
    """Контейнер результата для операций пакетной загрузки."""
    data: Dict[Any, Any]
    cache_hits: int = 0
    cache_misses: int = 0
    db_queries: int = 0
    execution_time_ms: float = 0.0


class DataLoader:
    """Базовый класс DataLoader для эффективной пакетной загрузки."""
    
    def __init__(self, cache_key_prefix: str = None, cache_ttl: int = 300):
        self.cache_key_prefix = cache_key_prefix or self.__class__.__name__
        self.cache_ttl = cache_ttl
        self._request_cache = {}
    
    def load(self, key: Any) -> Any:
        """Загружает один элемент по ключу."""
        if key in self._request_cache:
            return self._request_cache[key]
        
        cache_key = f"{self.cache_key_prefix}:{key}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self._request_cache[key] = cached_result
            return cached_result
        
        result = self._load_single(key)
        
        cache.set(cache_key, result, self.cache_ttl)
        self._request_cache[key] = result
        
        return result
    
    def load_many(self, keys: List[Any]) -> List[Any]:
        """Загружает несколько элементов по ключам."""
        if not keys:
            return []
        
        results = {}
        uncached_keys = []
        
        for key in keys:
            if key in self._request_cache:
                results[key] = self._request_cache[key]
            else:
                uncached_keys.append(key)
        
        if uncached_keys:
            cache_keys = [f"{self.cache_key_prefix}:{key}" for key in uncached_keys]
            cached_results = cache.get_many(cache_keys)
            
            still_uncached_keys = []
            for key in uncached_keys:
                cache_key = f"{self.cache_key_prefix}:{key}"
                if cache_key in cached_results:
                    results[key] = cached_results[cache_key]
                    self._request_cache[key] = cached_results[cache_key]
                else:
                    still_uncached_keys.append(key)
            
            if still_uncached_keys:
                batch_results = self._load_batch(still_uncached_keys)
                
                cache_data = {
                    f"{self.cache_key_prefix}:{key}": result
                    for key, result in batch_results.items()
                }
                
                for key, result in batch_results.items():
                    results[key] = result
                    self._request_cache[key] = result
                
                if cache_data:
                    cache.set_many(cache_data, self.cache_ttl)
        
        return [results.get(key) for key in keys]
    
    def _load_single(self, key: Any) -> Any:
        """Переопределите этот метод для реализации загрузки одного элемента."""
        raise NotImplementedError
    
    def _load_batch(self, keys: List[Any]) -> Dict[Any, Any]:
        """Переопределите этот метод для реализации пакетной загрузки."""
        raise NotImplementedError
    
    def clear_cache(self, key: Any = None):
        """Очищает кэш для конкретного ключа или всех ключей."""
        if key:
            cache_key = f"{self.cache_key_prefix}:{key}"
            cache.delete(cache_key)
            self._request_cache.pop(key, None)
        else:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{self.cache_key_prefix}:*")
            self._request_cache.clear()
    
    def _ensure_all_ids_in_results(self, results: Dict, requested_ids: List[Any], default_value: Any = None):
        """Убеждается, что все запрошенные ID присутствуют в результатах."""
        for requested_id in requested_ids:
            if requested_id not in results:
                results[requested_id] = default_value if default_value is not None else []


class SignalCardCategoriesLoader(DataLoader):
    """DataLoader для категорий SignalCard."""
    
    def __init__(self):
        super().__init__("signal_card_categories", cache_ttl=600)
    
    def _load_single(self, signal_card_id: int) -> List[Category]:
        """Загружает категории для одной карточки сигнала."""
        try:
            signal_card = SignalCard.objects.get(id=signal_card_id)
            return list(signal_card.categories.all())
        except SignalCard.DoesNotExist:
            return []
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, List[Category]]:
        """Загружает категории для нескольких карточек сигналов."""
        results = defaultdict(list)
        
        signal_cards = SignalCard.objects.filter(
            id__in=signal_card_ids
        ).prefetch_related('categories')
        
        for signal_card in signal_cards:
            results[signal_card.id] = list(signal_card.categories.all())
        
        self._ensure_all_ids_in_results(results, signal_card_ids, [])
        return dict(results)


class SignalCardSignalsLoader(DataLoader):
    """DataLoader для сигналов SignalCard."""
    
    def __init__(self):
        super().__init__("signal_card_signals", cache_ttl=300)
    
    def _load_single(self, signal_card_id: int) -> List[Signal]:
        """Загружает сигналы для одной карточки сигнала."""
        return list(Signal.objects.filter(
            signal_card_id=signal_card_id
        ).select_related('participant', 'associated_participant').order_by('-created_at'))
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, List[Signal]]:
        """Загружает сигналы для нескольких карточек сигналов."""
        results = defaultdict(list)
        
        signals = Signal.objects.filter(
            signal_card_id__in=signal_card_ids
        ).select_related('participant', 'associated_participant').order_by('-created_at')
        
        for signal in signals:
            results[signal.signal_card_id].append(signal)
        
        self._ensure_all_ids_in_results(results, signal_card_ids, [])
        return dict(results)


class SignalCardParticipantsLoader(DataLoader):
    """DataLoader для участников SignalCard."""
    
    def __init__(self):
        super().__init__("signal_card_participants", cache_ttl=600)
    
    def _load_single(self, signal_card_id: int) -> List[Participant]:
        """Загружает участников для одной карточки сигнала."""
        participant_ids = set()
        
        signals = Signal.objects.filter(signal_card_id=signal_card_id)
        for signal in signals:
            if signal.participant_id:
                participant_ids.add(signal.participant_id)
            if signal.associated_participant_id:
                participant_ids.add(signal.associated_participant_id)
        
        return list(Participant.objects.filter(id__in=participant_ids))
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, List[Participant]]:
        """Загружает участников для нескольких карточек сигналов."""
        results = defaultdict(list)
        
        signals = Signal.objects.filter(
            signal_card_id__in=signal_card_ids
        ).select_related('participant', 'associated_participant')
        
        card_participants = defaultdict(set)
        for signal in signals:
            if signal.participant:
                card_participants[signal.signal_card_id].add(signal.participant)
            if signal.associated_participant:
                card_participants[signal.signal_card_id].add(signal.associated_participant)
        
        for signal_card_id, participants in card_participants.items():
            results[signal_card_id] = list(participants)
        
        self._ensure_all_ids_in_results(results, signal_card_ids, [])
        return dict(results)


class UserDataLoader(DataLoader):
    """DataLoader для пользовательских данных (избранное, заметки, статус удаления)."""
    
    def __init__(self, user_id: int):
        super().__init__(f"user_data_{user_id}", cache_ttl=60)
        self.user_id = user_id
    
    def _load_single(self, signal_card_id: int) -> Dict[str, Any]:
        """Загружает пользовательские данные для одной карточки сигнала."""
        result = {
            'is_favorited': False,
            'is_deleted': False,
            'user_note': None,
            'folders': []
        }
        
        folder_cards = FolderCard.objects.filter(
            folder__user_id=self.user_id,
            signal_card_id=signal_card_id
        ).select_related('folder')
        
        if folder_cards.exists():
            result['is_favorited'] = True
            result['folders'] = [fc.folder for fc in folder_cards]
        
        result['is_deleted'] = DeletedCard.objects.filter(
            user_id=self.user_id,
            signal_card_id=signal_card_id
        ).exists()
        
        try:
            result['user_note'] = UserNote.objects.get(
                user_id=self.user_id,
                signal_card_id=signal_card_id
            )
        except UserNote.DoesNotExist:
            pass
        
        return result
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Загружает пользовательские данные для нескольких карточек сигналов."""
        results = {
            signal_card_id: {
                'is_favorited': False,
                'is_deleted': False,
                'user_note': None,
                'folders': []
            }
            for signal_card_id in signal_card_ids
        }
        
        folder_cards = FolderCard.objects.filter(
            folder__user_id=self.user_id,
            signal_card_id__in=signal_card_ids
        ).select_related('folder')
        
        card_folders = defaultdict(list)
        for fc in folder_cards:
            card_folders[fc.signal_card_id].append(fc.folder)
        
        for signal_card_id, folders in card_folders.items():
            results[signal_card_id]['is_favorited'] = True
            results[signal_card_id]['folders'] = folders
        
        deleted_card_ids = set(DeletedCard.objects.filter(
            user_id=self.user_id,
            signal_card_id__in=signal_card_ids
        ).values_list('signal_card_id', flat=True))
        
        for signal_card_id in deleted_card_ids:
            results[signal_card_id]['is_deleted'] = True
        
        user_notes = UserNote.objects.filter(
            user_id=self.user_id,
            signal_card_id__in=signal_card_ids
        )
        
        for note in user_notes:
            results[note.signal_card_id]['user_note'] = note
        
        return results


class ParticipantSavedStatusLoader(DataLoader):
    """DataLoader для статуса сохранения участника пользователем."""
    
    def __init__(self, user_id: int):
        super().__init__(f"participant_saved_{user_id}", cache_ttl=300)
        self.user_id = user_id
    
    def _load_single(self, participant_id: int) -> bool:
        """Проверяет, сохранен ли участник пользователем."""
        return SavedParticipant.objects.filter(
            user_id=self.user_id,
            participant_id=participant_id
        ).exists()
    
    def _load_batch(self, participant_ids: List[int]) -> Dict[int, bool]:
        """Проверяет статус сохранения для нескольких участников."""
        results = {participant_id: False for participant_id in participant_ids}
        
        saved_participant_ids = set(SavedParticipant.objects.filter(
            user_id=self.user_id,
            participant_id__in=participant_ids
        ).values_list('participant_id', flat=True))
        
        for participant_id in saved_participant_ids:
            results[participant_id] = True
        
        return results


class RemainingParticipantsCountLoader(DataLoader):
    """DataLoader для подсчета оставшихся участников с оптимизацией пакетной загрузки."""
    
    def __init__(self, user_id=None):
        super().__init__("remaining_participants_count", cache_ttl=300)
        self.user_id = user_id
        self.user = None
        if user_id:
            from profile.models import User
            try:
                self.user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
    
    def _load_single(self, signal_card_id: int) -> int:
        """Загружает количество оставшихся участников для одной карточки сигнала."""
        from .optimized_signal_resolver import get_remaining_participants_count
        return get_remaining_participants_count(signal_card_id, self.user)
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, int]:
        """Пакетная загрузка количества оставшихся участников для нескольких карточек."""
        from .optimized_signal_resolver import OptimizedSignalResolver
        
        resolver = OptimizedSignalResolver(self.user)
        results = {}
        
        signals_by_card = resolver.get_signals_for_cards_bulk(signal_card_ids, limit_participants=False)
        
        for card_id in signal_card_ids:
            signals = signals_by_card.get(card_id, [])
            
            all_participant_ids = set()
            for signal in signals:
                participant_id = signal.participant_id or signal.associated_participant_id
                if participant_id:
                    all_participant_ids.add(participant_id)
            
            seen_participants = set()
            first_8_participant_ids = set()
            
            for signal in sorted(signals, key=lambda s: s.created_at, reverse=True):
                participant_id = signal.participant_id or signal.associated_participant_id
                if participant_id and participant_id not in seen_participants:
                    seen_participants.add(participant_id)
                    first_8_participant_ids.add(participant_id)
                    if len(first_8_participant_ids) >= 8:
                        break
            
            remaining_count = len(all_participant_ids - first_8_participant_ids)
            results[card_id] = remaining_count
        
        return results


class LatestSignalDateLoader(DataLoader):
    """DataLoader для дат последних сигналов с оптимизацией пакетной загрузки."""
    
    def __init__(self):
        super().__init__("latest_signal_date", cache_ttl=600)
    
    def _load_single(self, signal_card_id: int) -> Optional[datetime]:
        """Загружает дату последнего сигнала для одной карточки сигнала."""
        result = Signal.objects.filter(signal_card_id=signal_card_id).aggregate(
            latest_date=Max('created_at')
        )
        return result['latest_date']
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, Optional[datetime]]:
        """Пакетная загрузка дат последних сигналов для нескольких карточек."""
        results = Signal.objects.filter(
            signal_card_id__in=signal_card_ids
        ).values('signal_card_id').annotate(
            latest_date=Max('created_at')
        ).values_list('signal_card_id', 'latest_date')
        
        result_dict = dict(results)
        self._ensure_all_ids_in_results(result_dict, signal_card_ids, None)
        
        return result_dict


class SignalCardUserDataBulkLoader(DataLoader):
    """Улучшенный загрузчик пользовательских данных с пакетной предзагрузкой."""
    
    def __init__(self, user_id):
        super().__init__(f"user_data_bulk_{user_id}", cache_ttl=300)
        self.user_id = user_id
        self.user = None
        if user_id:
            from profile.models import User
            try:
                self.user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
    
    def _load_single(self, signal_card_id: int) -> Dict:
        """Загружает пользовательские данные для одной карточки сигнала."""
        if not self.user or not hasattr(self.user, 'id') or self.user.id is None:
            return {'isFavorited': False, 'isDeleted': False, 'userNote': None}
        
        try:
            is_favorited = FolderCard.objects.filter(
                folder__user=self.user, signal_card_id=signal_card_id
            ).exists()
            
            is_deleted = DeletedCard.objects.filter(
                user=self.user, signal_card_id=signal_card_id
            ).exists()
            
            try:
                user_note = UserNote.objects.get(
                    user=self.user, signal_card_id=signal_card_id
                )
            except UserNote.DoesNotExist:
                user_note = None
            
            return {
                'isFavorited': is_favorited,
                'isDeleted': is_deleted,
                'userNote': user_note
            }
        except Exception as e:
            logger.error(f"Ошибка в SignalCardUserDataBulkLoader._load_single: {e}", exc_info=True)
            return {'isFavorited': False, 'isDeleted': False, 'userNote': None}
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, Dict]:
        """Пакетная загрузка пользовательских данных для нескольких карточек сигналов."""
        if not self.user or not hasattr(self.user, 'id') or self.user.id is None:
            return {card_id: {'isFavorited': False, 'isDeleted': False, 'userNote': None} 
                    for card_id in signal_card_ids}
        
        try:
            user_notes = {
                note.signal_card_id: note
                for note in UserNote.objects.filter(
                    user=self.user, signal_card_id__in=signal_card_ids
                )
            }
            
            folder_cards = set(
                FolderCard.objects.filter(
                    folder__user=self.user, signal_card_id__in=signal_card_ids
                ).values_list('signal_card_id', flat=True)
            )
            
            deleted_cards = set(
                DeletedCard.objects.filter(
                    user=self.user, signal_card_id__in=signal_card_ids
                ).values_list('signal_card_id', flat=True)
            )
            
            return {
                card_id: {
                    'isFavorited': card_id in folder_cards,
                    'isDeleted': card_id in deleted_cards,
                    'userNote': user_notes.get(card_id, None)
                }
                for card_id in signal_card_ids
            }
        except Exception as e:
            logger.error(f"Ошибка в SignalCardUserDataBulkLoader._load_batch: {e}", exc_info=True)
            return {card_id: {'isFavorited': False, 'isDeleted': False, 'userNote': None} 
                    for card_id in signal_card_ids}


class ParticipantSourcesLoader(DataLoader):
    """DataLoader для источников участника."""
    
    def __init__(self):
        super().__init__("participant_sources", cache_ttl=600)
    
    def _load_single(self, participant_id: int) -> List:
        """Загружает источники для одного участника."""
        try:
            participant = Participant.objects.get(id=participant_id)
            return list(participant.sources.all())
        except Participant.DoesNotExist:
            return []
    
    def _load_batch(self, participant_ids: List[int]) -> Dict[int, List]:
        """Загружает источники для нескольких участников."""
        results = defaultdict(list)
        
        participants = Participant.objects.filter(
            id__in=participant_ids
        ).prefetch_related('sources')
        
        for participant in participants:
            results[participant.id] = list(participant.sources.all())
        
        self._ensure_all_ids_in_results(results, participant_ids, [])
        return dict(results)


class ParticipantChildrenLoader(DataLoader):
    """DataLoader для дочерних участников (ассоциации)."""
    
    def __init__(self):
        super().__init__("participant_children", cache_ttl=600)
    
    def _load_single(self, participant_id: int) -> List:
        """Загружает дочерние элементы для одного участника."""
        try:
            participant = Participant.objects.get(id=participant_id)
            return list(participant.associations.exclude(id=participant.id))
        except Participant.DoesNotExist:
            return []
    
    def _load_batch(self, participant_ids: List[int]) -> Dict[int, List]:
        """Загружает дочерние элементы для нескольких участников."""
        results = defaultdict(list)
        
        children = Participant.objects.filter(
            associated_with_id__in=participant_ids
        ).exclude(id__in=participant_ids)
        
        for child in children:
            if child.associated_with_id:
                results[child.associated_with_id].append(child)
        
        self._ensure_all_ids_in_results(results, participant_ids, [])
        return dict(results)


class ParticipantParentLoader(DataLoader):
    """DataLoader для родительского участника (associated_with)."""
    
    def __init__(self):
        super().__init__("participant_parent", cache_ttl=600)
    
    def _load_single(self, participant_id: int) -> Optional[Any]:
        """Загружает родителя для одного участника."""
        try:
            participant = Participant.objects.select_related('associated_with').get(id=participant_id)
            if participant.associated_with and participant.associated_with.id != participant.id:
                return participant.associated_with
            return None
        except Participant.DoesNotExist:
            return None
    
    def _load_batch(self, participant_ids: List[int]) -> Dict[int, Optional[Any]]:
        """Загружает родителей для нескольких участников."""
        results = {}
        
        participants = Participant.objects.filter(
            id__in=participant_ids
        ).select_related('associated_with')
        
        for participant in participants:
            if (participant.associated_with and 
                participant.associated_with.id != participant.id):
                results[participant.id] = participant.associated_with
            else:
                results[participant.id] = None
        
        self._ensure_all_ids_in_results(results, participant_ids, None)
        return results


class SignalCardTicketLoader(DataLoader):
    """DataLoader для существования тикета SignalCard."""
    
    def __init__(self, user_id: int):
        super().__init__(f"signal_card_ticket_{user_id}", cache_ttl=300)
        self.user_id = user_id
    
    def _load_single(self, signal_card_id: int) -> bool:
        """Проверяет, есть ли у пользователя тикет для карточки сигнала."""
        from profile.models import TicketForCard
        return TicketForCard.objects.filter(
            user_id=self.user_id,
            signal_card_id=signal_card_id
        ).exists()
    
    def _load_batch(self, signal_card_ids: List[int]) -> Dict[int, bool]:
        """Проверяет существование тикетов для нескольких карточек сигналов."""
        results = {signal_card_id: False for signal_card_id in signal_card_ids}
        
        from profile.models import TicketForCard
        ticket_card_ids = set(TicketForCard.objects.filter(
            user_id=self.user_id,
            signal_card_id__in=signal_card_ids
        ).values_list('signal_card_id', flat=True))
        
        for signal_card_id in ticket_card_ids:
            results[signal_card_id] = True
        
        return results


class DataLoaderManager:
    """Управляет экземплярами DataLoader для одного запроса."""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self._loaders = {}
        
        self._loaders['user_data'] = UserDataLoader(user_id) if user_id else None
        self._loaders['signal_card_participants'] = SignalCardParticipantsLoader()
        self._loaders['remaining_participants_count'] = RemainingParticipantsCountLoader(user_id)
        self._loaders['latest_signal_date'] = LatestSignalDateLoader()
        self._loaders['user_data_bulk'] = SignalCardUserDataBulkLoader(user_id) if user_id else None
        self._loaders['participant_sources'] = ParticipantSourcesLoader()
        self._loaders['participant_children'] = ParticipantChildrenLoader()
        self._loaders['participant_parent'] = ParticipantParentLoader()
        
        if user_id:
            self._loaders['signal_card_ticket'] = SignalCardTicketLoader(user_id)
    
    def get_signal_card_categories_loader(self) -> SignalCardCategoriesLoader:
        """Получает или создает SignalCardCategoriesLoader."""
        if 'categories' not in self._loaders:
            self._loaders['categories'] = SignalCardCategoriesLoader()
        return self._loaders['categories']
    
    def get_signal_card_signals_loader(self) -> SignalCardSignalsLoader:
        """Получает или создает SignalCardSignalsLoader."""
        if 'signals' not in self._loaders:
            self._loaders['signals'] = SignalCardSignalsLoader()
        return self._loaders['signals']
    
    def get_signal_card_participants_loader(self) -> SignalCardParticipantsLoader:
        """Получает SignalCardParticipantsLoader."""
        return self._loaders['signal_card_participants']
    
    def get_user_data_loader(self):
        """Получает загрузчик пользовательских данных для избранного, заметок и т.д."""
        return self._loaders.get('user_data')
    
    def get_participant_saved_status_loader(self) -> Optional[ParticipantSavedStatusLoader]:
        """Получает или создает ParticipantSavedStatusLoader если пользователь аутентифицирован."""
        if self.user_id is None:
            return None
        
        if 'participant_saved' not in self._loaders:
            self._loaders['participant_saved'] = ParticipantSavedStatusLoader(self.user_id)
        return self._loaders['participant_saved']
    
    def get_remaining_participants_count_loader(self):
        """Получает загрузчик количества оставшихся участников."""
        return self._loaders['remaining_participants_count']
    
    def get_latest_signal_date_loader(self):
        """Получает загрузчик даты последнего сигнала."""
        return self._loaders['latest_signal_date']
    
    def get_user_data_bulk_loader(self):
        """Получает загрузчик пользовательских данных для пакетной загрузки."""
        return self._loaders.get('user_data_bulk')
    
    def get_participant_sources_loader(self):
        """Получает загрузчик источников участника."""
        return self._loaders['participant_sources']
    
    def get_participant_children_loader(self):
        """Получает загрузчик дочерних участников."""
        return self._loaders['participant_children']
    
    def get_participant_parent_loader(self):
        """Получает загрузчик родительского участника."""
        return self._loaders['participant_parent']
    
    def get_signal_card_ticket_loader(self):
        """Получает загрузчик тикетов карточки сигнала (требует аутентифицированного пользователя)."""
        return self._loaders.get('signal_card_ticket')
    
    def clear_all_caches(self):
        """Очищает все кэши загрузчиков."""
        for loader in self._loaders.values():
            if loader:
                loader.clear_cache()


def get_dataloader_manager(info) -> DataLoaderManager:
    """
    Получает или создает DataLoaderManager для текущего запроса.
    
    Args:
        info: GraphQL resolve info
        
    Returns:
        Экземпляр DataLoaderManager
    """
    request = info.context.get('request')
    if not request:
        return DataLoaderManager()
    
    user_id = None
    if request.user and request.user.is_authenticated:
        user_id = request.user.id
    
    if not hasattr(request, '_dataloader_manager'):
        request._dataloader_manager = DataLoaderManager(user_id)
    
    return request._dataloader_manager


def load_signal_card_categories(info, signal_card_id: int) -> List[Category]:
    """Загружает категории для карточки сигнала используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_signal_card_categories_loader()
    return loader.load(signal_card_id)


def load_signal_card_signals(info, signal_card_id: int) -> List[Signal]:
    """Загружает сигналы для карточки сигнала используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_signal_card_signals_loader()
    return loader.load(signal_card_id)


def load_signal_card_participants(info, signal_card_id: int) -> List[Participant]:
    """Загружает участников для карточки сигнала используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_signal_card_participants_loader()
    return loader.load(signal_card_id)


def load_user_data(info, signal_card_id: int) -> Optional[Dict[str, Any]]:
    """Загружает пользовательские данные для карточки сигнала используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_user_data_loader()
    if loader:
        return loader.load(signal_card_id)
    return None


def load_participant_saved_status(info, participant_id: int) -> Optional[bool]:
    """Загружает статус сохранения участника используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_participant_saved_status_loader()
    if loader:
        return loader.load(participant_id)
    return None


def load_participant_sources(info, participant_id: int) -> List:
    """Загружает источники участника используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_participant_sources_loader()
    return loader.load(participant_id)


def load_participant_children(info, participant_id: int) -> List:
    """Загружает дочерние элементы участника используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_participant_children_loader()
    return loader.load(participant_id)


def load_participant_parent(info, participant_id: int) -> Optional[Any]:
    """Загружает родителя участника используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_participant_parent_loader()
    return loader.load(participant_id)


def load_signal_card_ticket_status(info, signal_card_id: int) -> Optional[bool]:
    """Загружает статус тикета карточки сигнала используя DataLoader."""
    manager = get_dataloader_manager(info)
    loader = manager.get_signal_card_ticket_loader()
    if loader:
        return loader.load(signal_card_id)
    return None
