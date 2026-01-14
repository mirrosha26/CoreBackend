"""
Система кэширования на уровне запросов для GraphQL запросов карточек сигналов.

Модуль предоставляет интеллектуальное кэширование дорогих результатов запросов
с стратегиями инвалидации кэша и мониторингом производительности.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class QueryCacheKeyBuilder:
    """Строит ключи кэша для GraphQL запросов."""
    
    @staticmethod
    def build_signal_cards_key(
        user_id: Optional[int],
        filters: Optional[Dict[str, Any]],
        pagination: Optional[Dict[str, Any]],
        card_type: str,
        sort_by: str,
        sort_order: str,
        include_signals: bool,
        query_complexity: int,
        display_preference: Optional[str] = None,
        folder_id: Optional[str] = None,
        folder_key: Optional[str] = None
    ) -> str:
        """Строит ключ кэша для запроса карточек сигналов."""
        key_data = {
            'user_id': user_id,
            'filters': filters or {},
            'pagination': pagination or {},
            'card_type': card_type,
            'sort_by': sort_by,
            'sort_order': sort_order,
            'include_signals': include_signals,
            'complexity': query_complexity,
            'display_preference': display_preference or 'ALL',
            'folder_id': folder_id,
            'folder_key': folder_key,
            'version': 'v4'
        }
        
        key_json = json.dumps(key_data, sort_keys=True, cls=DjangoJSONEncoder)
        key_hash = hashlib.md5(key_json.encode('utf-8')).hexdigest()
        
        return f"signal_cards_query:{key_hash}"
    
    @staticmethod
    def build_user_feed_key(
        user_id: int,
        filters: Optional[Dict[str, Any]],
        pagination: Optional[Dict[str, Any]],
        include_signals: bool,
        display_preference: Optional[str] = None
    ) -> str:
        """Строит ключ кэша для запроса ленты пользователя."""
        key_data = {
            'user_id': user_id,
            'filters': filters or {},
            'pagination': pagination or {},
            'include_signals': include_signals,
            'display_preference': display_preference or 'ALL',
            'query_type': 'user_feed',
            'version': 'v3'
        }
        
        key_json = json.dumps(key_data, sort_keys=True, cls=DjangoJSONEncoder)
        key_hash = hashlib.md5(key_json.encode('utf-8')).hexdigest()
        
        return f"user_feed_query:{key_hash}"
    
    @staticmethod
    def build_count_key(base_key: str) -> str:
        """Строит ключ кэша для подсчета из базового ключа запроса."""
        return f"{base_key}:count"


class QueryResultCache:
    """Управляет кэшированием результатов GraphQL запросов."""
    
    CACHE_TTL_MAP = {
        'lightweight': 900,
        'moderate': 600,
        'heavy': 300,
        'comprehensive': 180
    }
    
    DATA_TYPE_TTL = {
        'signal_cards': 300,
        'user_feed': 180,
        'filter_counts': 600,
        'user_data': 900
    }
    
    def __init__(self):
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0
        }
    
    def get_cached_result(self, cache_key: str, result_type: str = 'signal_cards') -> Optional[Any]:
        """Получает закэшированный результат запроса."""
        start_time = time.time()
        
        try:
            cached_data = cache.get(cache_key)
            
            if cached_data is not None:
                self.cache_stats['hits'] += 1
                
                if self._is_valid_cached_data(cached_data, result_type):
                    return cached_data['result']
                else:
                    cache.delete(cache_key)
                    logger.warning(f"Удалены невалидные данные кэша для {cache_key}")
            
            self.cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения кэша для {cache_key}: {e}")
            self.cache_stats['misses'] += 1
            return None
        finally:
            execution_time = (time.time() - start_time) * 1000
            if execution_time > 10:
                logger.warning(f"Медленное получение кэша для {cache_key}: {execution_time:.2f}мс")
    
    def set_cached_result(
        self, 
        cache_key: str, 
        result: Any, 
        result_type: str = 'signal_cards',
        query_complexity: str = 'moderate',
        custom_ttl: Optional[int] = None
    ) -> bool:
        """Кэширует результат запроса с соответствующим TTL."""
        start_time = time.time()
        
        try:
            if custom_ttl:
                ttl = custom_ttl
            else:
                complexity_ttl = self.CACHE_TTL_MAP.get(query_complexity, 300)
                data_type_ttl = self.DATA_TYPE_TTL.get(result_type, 300)
                ttl = min(complexity_ttl, data_type_ttl)
            
            cache_data = {
                'result': result,
                'cached_at': time.time(),
                'ttl': ttl,
                'result_type': result_type,
                'query_complexity': query_complexity
            }
            
            cache.set(cache_key, cache_data, ttl)
            self.cache_stats['sets'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки кэша для {cache_key}: {e}")
            return False
        finally:
            execution_time = (time.time() - start_time) * 1000
            if execution_time > 10:
                logger.warning(f"Медленная установка кэша для {cache_key}: {execution_time:.2f}мс")
    
    def invalidate_user_cache(self, user_id: int):
        """Инвалидирует все записи кэша для конкретного пользователя."""
        try:
            logger.info(f"Инвалидация кэша запросов для пользователя {user_id}")
            
            specific_keys_to_delete = [
                f"saved_participants:{user_id}",
                f"feed_participants:{user_id}",
                f"requested_participants:{user_id}",
                f"user_context:{user_id}:saved_participants:v2",
                f"user_context:{user_id}:feed_config:v2",
                f"user_context:{user_id}:privacy_filter:v2",
                f"user_context:{user_id}:bulk_data:v2",
                f"user_context:{user_id}:display_pref:v1",
            ]
            
            cache.delete_many(specific_keys_to_delete)
            cache.clear()
            logger.info(f"Очищен весь кэш для обеспечения консистентности данных пользователя {user_id}")
    
            self.cache_stats['invalidations'] += 1
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации кэша для пользователя {user_id}: {e}")
            try:
                cache.clear()
                logger.warning("Очищен весь кэш из-за ошибки инвалидации")
            except Exception as clear_error:
                logger.error(f"Не удалось очистить кэш: {clear_error}")
    
    def invalidate_signal_cache(self, signal_card_ids: List[int]):
        """Инвалидирует записи кэша, связанные с конкретными карточками сигналов."""
        try:
            self.cache_stats['invalidations'] += len(signal_card_ids)
        except Exception as e:
            logger.error(f"Ошибка инвалидации кэша для карточек сигналов {signal_card_ids}: {e}")
    
    def _is_valid_cached_data(self, cached_data: Dict[str, Any], expected_type: str) -> bool:
        """Проверяет структуру закэшированных данных."""
        required_fields = ['result', 'cached_at', 'result_type']
        
        if not all(field in cached_data for field in required_fields):
            return False
        
        if cached_data['result_type'] != expected_type:
            return False
        
        cache_age = time.time() - cached_data['cached_at']
        max_age = cached_data.get('ttl', 300) * 2
        
        return cache_age < max_age
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получает статистику производительности кэша."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests
        }


class CachedQueryManager:
    """Высокоуровневый менеджер для кэшированных GraphQL запросов."""
    
    def __init__(self):
        self.cache = QueryResultCache()
        self.key_builder = QueryCacheKeyBuilder()
    
    def get_or_compute_signal_cards(
        self,
        compute_func,
        user_id: Optional[int],
        filters: Optional[Dict[str, Any]],
        pagination: Optional[Dict[str, Any]],
        card_type: str,
        sort_by: str,
        sort_order: str,
        include_signals: bool,
        query_complexity: str = 'moderate',
        display_preference: Optional[str] = None,
        folder_id: Optional[str] = None,
        folder_key: Optional[str] = None
    ) -> Any:
        """Получает карточки сигналов из кэша или вычисляет, если не закэшировано."""
        cache_key = self.key_builder.build_signal_cards_key(
            user_id=user_id,
            filters=filters,
            pagination=pagination,
            card_type=card_type,
            sort_by=sort_by,
            sort_order=sort_order,
            include_signals=include_signals,
            query_complexity=self._get_complexity_score(query_complexity),
            display_preference=display_preference,
            folder_id=folder_id,
            folder_key=folder_key
        )
        
        cached_result = self.cache.get_cached_result(cache_key, 'signal_cards')
        if cached_result is not None:
            return cached_result
        
        start_time = time.time()
        result = compute_func()
        computation_time = (time.time() - start_time) * 1000
        
        if computation_time > 100 or query_complexity in ['heavy', 'comprehensive']:
            self.cache.set_cached_result(
                cache_key=cache_key,
                result=result,
                result_type='signal_cards',
                query_complexity=query_complexity
            )
        
        return result
    
    def get_or_compute_user_feed(
        self,
        compute_func,
        user_id: int,
        filters: Optional[Dict[str, Any]],
        pagination: Optional[Dict[str, Any]],
        include_signals: bool,
        display_preference: Optional[str] = None
    ) -> Any:
        """Получает ленту пользователя из кэша или вычисляет, если не закэшировано."""
        cache_key = self.key_builder.build_user_feed_key(
            user_id=user_id,
            filters=filters,
            pagination=pagination,
            include_signals=include_signals,
            display_preference=display_preference
        )
        
        cached_result = self.cache.get_cached_result(cache_key, 'user_feed')
        if cached_result is not None:
            return cached_result
        
        result = compute_func()
        
        self.cache.set_cached_result(
            cache_key=cache_key,
            result=result,
            result_type='user_feed',
            query_complexity='heavy'
        )
        
        return result
    
    def _get_complexity_score(self, complexity: str) -> int:
        """Преобразует строку сложности в числовую оценку."""
        complexity_scores = {
            'lightweight': 1,
            'moderate': 5,
            'heavy': 15,
            'comprehensive': 25
        }
        return complexity_scores.get(complexity, 5)
    
    def invalidate_user_data(self, user_id: int):
        """Инвалидирует все закэшированные данные для пользователя."""
        self.cache.invalidate_user_cache(user_id)
    
    def invalidate_signal_data(self, signal_card_ids: List[int]):
        """Инвалидирует закэшированные данные для конкретных карточек сигналов."""
        self.cache.invalidate_signal_cache(signal_card_ids)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получает статистику производительности кэша."""
        return self.cache.get_cache_stats()


_global_cache_manager = None


def get_cache_manager() -> CachedQueryManager:
    """Получает глобальный экземпляр менеджера кэша."""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CachedQueryManager()
    return _global_cache_manager 