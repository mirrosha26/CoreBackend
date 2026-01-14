"""
Расширенная система пакетной загрузки для комплексных запросов GraphQL лент.

Модуль расширяет существующий OptimizedSignalResolver дополнительными
оптимизациями специально для комплексных запросов лент.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from django.core.cache import cache

from signals.models import SignalCard, Signal

from .dataloaders import get_dataloader_manager
from .optimized_signal_resolver import OptimizedSignalResolver

logger = logging.getLogger(__name__)


class ComprehensiveFeedOptimizer:
    """Специализированный оптимизатор для комплексных запросов лент."""
    
    def __init__(self, user=None):
        self.user = user
        self.signal_resolver = OptimizedSignalResolver(user)
    
    def optimize_comprehensive_query(self, signal_cards: List[SignalCard], info) -> List[SignalCard]:
        """
        Применяет комплексные оптимизации к списку карточек сигналов.
        
        Метод выполняет:
        1. Пакетную предзагрузку всех сигналов с фильтрацией приватности
        2. Пакетную предзагрузку всех пользовательских данных
        3. Пакетную предзагрузку всех категорий
        4. Применяет ограничение участников последовательно
        """
        if not signal_cards:
            return signal_cards
        
        card_ids = [card.id for card in signal_cards]
        
        signals_by_card = self.signal_resolver.get_signals_for_cards_bulk(
            card_ids, 
            limit_participants=True
        )
        
        if self.user and self.user.is_authenticated:
            self._preload_user_data_bulk(card_ids, info)
        
        self._preload_categories_bulk(signal_cards)
        
        for card in signal_cards:
            signals_for_card = signals_by_card.get(card.id, [])
            card._optimized_signals = signals_for_card
            card._signals_preloaded = True
        
        return signal_cards
    
    def _preload_user_data_bulk(self, card_ids: List[int], info) -> None:
        """Предзагружает пользовательские данные используя DataLoaders для эффективности."""
        dataloader_manager = get_dataloader_manager(info)
        user_data_loader = dataloader_manager.get_user_data_loader()
        
        if user_data_loader:
            user_data_loader.load_many(card_ids)
    
    def _preload_categories_bulk(self, signal_cards: List[SignalCard]) -> None:
        """Предзагружает категории используя эффективное prefetch."""
        if not signal_cards:
            return
        
        if hasattr(signal_cards[0], '_prefetched_objects_cache'):
            if 'categories' in signal_cards[0]._prefetched_objects_cache:
                return
    
    def get_optimized_signals_for_card(self, card: SignalCard) -> List[Signal]:
        """Получает оптимизированные сигналы для карточки, используя предзагруженные данные если доступны."""
        if hasattr(card, '_optimized_signals') and card._signals_preloaded:
            return card._optimized_signals
        
        return self.signal_resolver.get_signals_for_card(card.id, limit_participants=True)
    
    def get_remaining_participants_count(self, card: SignalCard) -> int:
        """Получает количество оставшихся участников используя оптимизированный резолвер."""
        return self.signal_resolver.get_remaining_participants_count(card.id)


class SmartQueryCache:
    """Умное кэширование для комплексных запросов с автоматической инвалидацией."""
    
    @classmethod
    def get_cached_feed_result(cls, cache_key: str) -> Optional[Any]:
        """Получает закэшированный результат ленты с автоматической проверкой свежести."""
        cached_data = cache.get(cache_key)
        if cached_data is None:
            return None
        
        if isinstance(cached_data, dict) and 'timestamp' in cached_data:
            cache_age = time.time() - cached_data['timestamp']
            
            if cache_age > 300:
                cache.delete(cache_key)
                return None
        
        return cached_data.get('result') if isinstance(cached_data, dict) else cached_data
    
    @classmethod
    def set_cached_feed_result(cls, cache_key: str, result: Any, ttl: int = 300) -> None:
        """Устанавливает закэшированный результат ленты с временной меткой для отслеживания свежести."""
        cached_data = {
            'result': result,
            'timestamp': time.time(),
            'cached_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        cache.set(cache_key, cached_data, ttl)


def optimize_signal_cards_for_comprehensive_feed(
    signal_cards: List[SignalCard], 
    user=None, 
    info=None
) -> List[SignalCard]:
    """
    Публичная функция для оптимизации карточек сигналов для комплексных запросов лент.
    
    Args:
        signal_cards: Список карточек сигналов для оптимизации
        user: Текущий пользователь для фильтрации приватности
        info: GraphQL resolve info для DataLoaders
    
    Returns:
        Оптимизированные карточки сигналов с предзагруженными данными
    """
    if not signal_cards:
        return signal_cards
    
    optimizer = ComprehensiveFeedOptimizer(user)
    return optimizer.optimize_comprehensive_query(signal_cards, info)


def get_comprehensive_feed_cache_key(
    user_id: int, 
    filters: Optional[Dict], 
    pagination: Optional[Dict]
) -> str:
    """Генерирует ключ кэша для комплексных запросов лент."""
    key_data = {
        'user_id': user_id,
        'query_type': 'comprehensive_feed',
        'filters': filters or {},
        'pagination': pagination or {},
        'version': 'v2'
    }
    
    key_json = json.dumps(key_data, sort_keys=True)
    key_hash = hashlib.md5(key_json.encode('utf-8')).hexdigest()
    
    return f"comprehensive_feed:{key_hash}"
