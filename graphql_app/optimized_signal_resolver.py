"""
Оптимизированный резолвер сигналов для комплексных GraphQL запросов лент.

Модуль предоставляет оптимизированную загрузку сигналов с:
- Фильтрацией приватности на уровне БД
- Пакетным ограничением участников
- Кэшированием на уровне запросов
- Минимальными итерациями в Python
"""

import logging
from collections import defaultdict
from typing import Dict, List

from django.core.cache import cache
from django.db.models import Q, Case, When, IntegerField, Window, Value
from django.db.models.functions import RowNumber

from signals.models import Signal

logger = logging.getLogger(__name__)


class OptimizedSignalResolver:
    """Оптимизированный резолвер для загрузки сигналов с пакетными операциями."""
    
    def __init__(self, user=None):
        self.user = user
        self.privacy_filter = self._build_privacy_filter()
    
    def _build_privacy_filter(self) -> Q:
        """
        Создает фильтр приватности Q для фильтрации на уровне БД.
        
        ВАЖНО: Должен совпадать с логикой приватности из queries.py
        _filter_cards_with_accessible_signals для предотвращения несоответствий в подсчете участников.
        """
        return Q(participant__isnull=False) | Q(associated_participant__isnull=False)
    
    def get_signals_for_card(self, signal_card_id: int, limit_participants: bool = False) -> List[Signal]:
        """
        Получает сигналы для одной карточки с оптимизированной фильтрацией.
        
        Когда limit_participants=True, возвращает снимок из 8 сигналов в хронологическом порядке
        (от новых к старым), сохраняя только самый старый сигнал для каждого участника при дубликатах.
        """
        cache_key = f"signals_card:{signal_card_id}:user:{self.user.id if self.user else 'anon'}:limit:{limit_participants}"
        
        cached_signals = cache.get(cache_key)
        if cached_signals is not None:
            return cached_signals
        
        signals_qs = Signal.objects.filter(
            signal_card_id=signal_card_id
        ).filter(
            self.privacy_filter
        ).select_related(
            'participant', 
            'associated_participant', 
            'signal_type'
        ).order_by('-created_at')
        
        if limit_participants:
            signals = self._limit_participants_efficiently(signals_qs)
        else:
            signals = list(signals_qs)
        
        cache.set(cache_key, signals, 180)
        return signals
    
    def get_signals_for_cards_bulk(self, signal_card_ids: List[int], limit_participants: bool = False) -> Dict[int, List[Signal]]:
        """
        Получает сигналы для нескольких карточек эффективно используя пакетные операции с умным кэшированием.
        
        Когда limit_participants=True, возвращает снимок из 8 сигналов на карточку в хронологическом порядке
        (от новых к старым), сохраняя только самый старый сигнал для каждого участника при дубликатах.
        """
        cache_keys = {}
        cached_results = {}
        uncached_card_ids = []
        
        for card_id in signal_card_ids:
            cache_key = f"signals_card:{card_id}:user:{self.user.id if self.user else 'anon'}:limit:{limit_participants}:v2"
            cache_keys[card_id] = cache_key
            
            cached_signals = cache.get(cache_key)
            if cached_signals is not None and self._verify_cached_signals_integrity(cached_signals):
                cached_results[card_id] = cached_signals
            else:
                uncached_card_ids.append(card_id)
                if cached_signals is not None:
                    cache.delete(cache_key)
        
        uncached_results = {}
        if uncached_card_ids:
            uncached_results = self._fetch_signals_bulk(uncached_card_ids, limit_participants)
            
            for card_id, signals in uncached_results.items():
                if self._verify_cached_signals_integrity(signals):
                    cache.set(cache_keys[card_id], signals, 180)
        
        all_results = {**cached_results, **uncached_results}
        
        for card_id in signal_card_ids:
            if card_id not in all_results:
                all_results[card_id] = []
        
        return all_results
    
    def _verify_cached_signals_integrity(self, signals: List[Signal]) -> bool:
        """Проверяет, что закэшированные сигналы сохраняют корректные связи с участниками."""
        if not signals:
            return True
        
        for signal in signals[:3]:
            if signal.participant_id:
                if not hasattr(signal, 'participant') or signal.participant is None:
                    return False
            if signal.associated_participant_id:
                if not hasattr(signal, 'associated_participant') or signal.associated_participant is None:
                    return False
        
        return True
    
    def _fetch_signals_bulk(self, signal_card_ids: List[int], limit_participants: bool) -> Dict[int, List[Signal]]:
        """Загружает сигналы для нескольких карточек из БД."""
        signals_qs = Signal.objects.filter(
            signal_card_id__in=signal_card_ids
        ).filter(
            self.privacy_filter
        ).select_related(
            'participant', 
            'associated_participant', 
            'signal_type'
        ).order_by('signal_card_id', '-created_at')
        
        if limit_participants:
            return self._apply_participant_limiting_bulk(signals_qs, signal_card_ids)
        else:
            results = defaultdict(list)
            for signal in signals_qs:
                results[signal.signal_card_id].append(signal)
            return dict(results)
    
    def _limit_participants_efficiently(self, signals_qs) -> List[Signal]:
        """
        Применяет ограничение снимка из 8 сигналов эффективно используя операции БД с оконными функциями.
        
        Возвращает сигналы в хронологическом порядке (от новых к старым) и берет снимок из 8 сигналов.
        При дубликатах (один участник) сохраняет только самый старый сигнал.
        """
        try:
            signals_with_participant_rank = signals_qs.annotate(
                effective_participant_id=Case(
                    When(participant_id__isnull=False, then='participant_id'),
                    When(associated_participant_id__isnull=False, then='associated_participant_id'),
                    default=Value(None),
                    output_field=IntegerField()
                ),
                participant_signal_rank=Window(
                    expression=RowNumber(),
                    partition_by=['effective_participant_id'],
                    order_by=['created_at']
                )
            )
            
            oldest_signals_per_entity = signals_with_participant_rank.filter(
                participant_signal_rank=1
            ).order_by('-created_at')
            
            return list(oldest_signals_per_entity[:8])
            
        except (ImportError, AttributeError) as e:
            logger.warning(f"Оконные функции недоступны, используется Python fallback: {e}")
            return self._limit_participants_python_fallback(signals_qs)
    
    def _limit_participants_python_fallback(self, signals_qs) -> List[Signal]:
        """
        Fallback ограничение снимка сигналов используя Python логику для совместимости с Django.
        
        Возвращает сигналы в хронологическом порядке (от новых к старым) и берет снимок из 8 сигналов.
        При дубликатах (один участник) сохраняет только самый старый сигнал.
        """
        signals_by_entity = defaultdict(list)
        
        for signal in signals_qs:
            entity_id = signal.participant_id or signal.associated_participant_id
            if entity_id:
                signals_by_entity[entity_id].append(signal)
        
        oldest_signals_per_entity = [
            min(signals, key=lambda s: s.created_at)
            for signals in signals_by_entity.values()
        ]
        
        oldest_signals_per_entity.sort(key=lambda s: s.created_at, reverse=True)
        return oldest_signals_per_entity[:8]
    
    def _apply_participant_limiting_bulk(self, signals_qs, signal_card_ids: List[int]) -> Dict[int, List[Signal]]:
        """
        Применяет ограничение снимка сигналов к пакетным сигналам эффективно используя оконные функции БД.
        
        Возвращает сигналы в хронологическом порядке (от новых к старым) и берет снимок из 8 сигналов на карточку.
        При дубликатах (один участник) сохраняет только самый старый сигнал.
        """
        try:
            signals_with_ranks = signals_qs.annotate(
                effective_participant_id=Case(
                    When(participant_id__isnull=False, then='participant_id'),
                    When(associated_participant_id__isnull=False, then='associated_participant_id'),
                    default=Value(None),
                    output_field=IntegerField()
                ),
                participant_signal_rank=Window(
                    expression=RowNumber(),
                    partition_by=['signal_card_id', 'effective_participant_id'],
                    order_by=['created_at']
                )
            )
            
            oldest_signals_per_participant = signals_with_ranks.filter(
                participant_signal_rank=1
            ).order_by('signal_card_id', '-created_at')
            
            results = defaultdict(list)
            current_card_id = None
            current_card_signals = []
            
            for signal in oldest_signals_per_participant:
                if current_card_id is None:
                    current_card_id = signal.signal_card_id
                
                if signal.signal_card_id != current_card_id:
                    results[current_card_id] = current_card_signals[:8]
                    current_card_id = signal.signal_card_id
                    current_card_signals = []
                
                current_card_signals.append(signal)
            
            if current_card_id is not None:
                results[current_card_id] = current_card_signals[:8]
            
            for card_id in signal_card_ids:
                if card_id not in results:
                    results[card_id] = []
            
            return dict(results)
            
        except (ImportError, AttributeError) as e:
            logger.warning(f"Оконные функции недоступны для пакетного ограничения, используется Python fallback: {e}")
            return self._apply_participant_limiting_bulk_fallback(signals_qs, signal_card_ids)
    
    def _apply_participant_limiting_bulk_fallback(self, signals_qs, signal_card_ids: List[int]) -> Dict[int, List[Signal]]:
        """
        Fallback пакетное ограничение снимка сигналов используя Python логику.
        
        Возвращает сигналы в хронологическом порядке (от новых к старым) и берет снимок из 8 сигналов на карточку.
        При дубликатах (один участник) сохраняет только самый старый сигнал.
        """
        signals_by_card = defaultdict(list)
        for signal in signals_qs:
            signals_by_card[signal.signal_card_id].append(signal)
        
        results = {}
        for card_id in signal_card_ids:
            card_signals = signals_by_card.get(card_id, [])
            results[card_id] = self._limit_participants_python_fallback(card_signals) if card_signals else []
        
        return results
    
    def get_remaining_participants_count(self, signal_card_id: int) -> int:
        """
        Получает количество участников за пределами первых 8 сигналов эффективно.
        
        ВАЖНО: Должен использовать ту же логику выбора сигналов, что и ограничение сигналов,
        чтобы обеспечить согласованность между отображаемыми сигналами и подсчетом.
        Поскольку мы берем снимок из 8 сигналов (не 8 участников), это считает участников,
        у которых есть сигналы за пределами снимка из 8 сигналов.
        """
        cache_key = f"remaining_participants:{signal_card_id}:user:{self.user.id if self.user else 'anon'}"
        
        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return cached_count
        
        signals_qs = Signal.objects.filter(
            signal_card_id=signal_card_id
        ).filter(
            self.privacy_filter
        ).order_by('-created_at')
        
        try:
            signals_with_participant_rank = signals_qs.annotate(
                effective_participant_id=Case(
                    When(participant_id__isnull=False, then='participant_id'),
                    default='associated_participant_id',
                    output_field=IntegerField()
                ),
                participant_signal_rank=Window(
                    expression=RowNumber(),
                    partition_by=['effective_participant_id'],
                    order_by=['created_at']
                )
            )
            
            oldest_signals_per_participant = signals_with_participant_rank.filter(
                participant_signal_rank=1
            ).order_by('-created_at')
            
            snapshot_signals = list(oldest_signals_per_participant[:8])
            snapshot_participant_ids = {
                signal.participant_id or signal.associated_participant_id
                for signal in snapshot_signals
                if signal.participant_id or signal.associated_participant_id
            }
            
        except (ImportError, AttributeError):
            signals_by_participant = defaultdict(list)
            for signal in signals_qs:
                participant_id = signal.participant_id or signal.associated_participant_id
                if participant_id:
                    signals_by_participant[participant_id].append(signal)
            
            oldest_signals_per_participant = [
                min(signals, key=lambda s: s.created_at)
                for signals in signals_by_participant.values()
            ]
            
            oldest_signals_per_participant.sort(key=lambda s: s.created_at, reverse=True)
            snapshot_signals = oldest_signals_per_participant[:8]
            
            snapshot_participant_ids = {
                signal.participant_id or signal.associated_participant_id
                for signal in snapshot_signals
                if signal.participant_id or signal.associated_participant_id
            }
        
        all_participant_ids = {
            signal.participant_id or signal.associated_participant_id
            for signal in signals_qs
            if signal.participant_id or signal.associated_participant_id
        }
        
        remaining_count = len(all_participant_ids - snapshot_participant_ids)
        cache.set(cache_key, remaining_count, 300)
        
        return remaining_count


def get_optimized_signals_for_cards(signal_card_ids: List[int], user=None, limit_participants: bool = False) -> Dict[int, List[Signal]]:
    """
    Публичная функция для получения оптимизированных сигналов для нескольких карточек.
    
    Args:
        signal_card_ids: Список ID карточек сигналов
        user: Пользователь для фильтрации приватности
        limit_participants: Брать ли снимок из 8 сигналов на карточку (от новых к старым,
                          сохраняя только самый старый сигнал для каждого участника при дубликатах)
    
    Returns:
        Словарь, сопоставляющий ID карточки со списком сигналов
    """
    resolver = OptimizedSignalResolver(user)
    return resolver.get_signals_for_cards_bulk(signal_card_ids, limit_participants)


def get_optimized_signals_for_card(signal_card_id: int, user=None, limit_participants: bool = False) -> List[Signal]:
    """
    Публичная функция для получения оптимизированных сигналов для одной карточки.
    
    Args:
        signal_card_id: ID карточки сигнала
        user: Пользователь для фильтрации приватности
        limit_participants: Брать ли снимок из 8 сигналов (от новых к старым,
                          сохраняя только самый старый сигнал для каждого участника при дубликатах)
    
    Returns:
        Список сигналов для карточки
    """
    resolver = OptimizedSignalResolver(user)
    return resolver.get_signals_for_card(signal_card_id, limit_participants)


def get_remaining_participants_count(signal_card_id: int, user=None) -> int:
    """
    Публичная функция для получения количества оставшихся участников эффективно.
    
    Args:
        signal_card_id: ID карточки сигнала
        user: Пользователь для фильтрации приватности
    
    Returns:
        Количество участников, у которых есть сигналы за пределами снимка из 8 сигналов
    """
    resolver = OptimizedSignalResolver(user)
    return resolver.get_remaining_participants_count(signal_card_id) 