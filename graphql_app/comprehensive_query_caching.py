"""
Расширенное кэширование запросов для комплексных лент.

Модуль расширяет существующую систему кэширования запросов
с оптимизациями для комплексных паттернов лент.
"""

import hashlib
import json
import logging
import re
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

from .cache_monitoring import get_cache_key_registry, get_cache_memory_monitor

logger = logging.getLogger(__name__)


class ComprehensiveFeedCacheManager:
    """Расширенный менеджер кэша для комплексных запросов лент с защитой памяти."""
    
    def __init__(self):
        self.cache_ttl_comprehensive = getattr(settings, 'COMPREHENSIVE_FEED_CACHE_TTL', 300)
        self.cache_ttl_overview = getattr(settings, 'FEED_OVERVIEW_CACHE_TTL', 900)
        
        self.memory_monitor = get_cache_memory_monitor()
        self.key_registry = get_cache_key_registry()
        
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_sets': 0,
            'memory_rejections': 0,
            'size_rejections': 0
        }
    
    def get_or_compute_comprehensive_feed(
        self,
        compute_func,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None,
        include_signals: bool = True,
        query_complexity: str = 'comprehensive',
        display_preference: Optional[str] = None,
        bypass_personal_filters: bool = True
    ) -> Any:
        """
        Получает комплексную ленту из кэша или вычисляет с интеллектуальной стратегией кэширования.
        
        Использует многоуровневое кэширование:
        1. Кэш уровня страницы для точной пагинации
        2. Базовый кэш запроса для тех же фильтров, другой пагинации
        3. Умная инвалидация на основе активности пользователя
        """
        page_cache_key = self._build_page_cache_key(
            user_id, filters, pagination, include_signals, display_preference, bypass_personal_filters
        )
        base_cache_key = self._build_base_cache_key(
            user_id, filters, include_signals, display_preference, bypass_personal_filters
        )
        
        cached_result = self._get_cached_result(page_cache_key)
        if cached_result is not None:
            self.stats['cache_hits'] += 1
            logger.debug(f"Попадание в кэш для ключа страницы: {page_cache_key[:50]}...")
            return cached_result
        
        base_cached_result = self._get_cached_result(base_cache_key)
        if base_cached_result is not None and self._can_extract_page_from_base(base_cached_result, pagination):
            self.stats['cache_hits'] += 1
            logger.debug(f"Попадание в кэш для базового ключа, извлечение страницы: {base_cache_key[:50]}...")
            page_result = self._extract_page_from_base(base_cached_result, pagination)
            self._set_cached_result(page_cache_key, page_result, ttl=self.cache_ttl_comprehensive, user_id=user_id)
            return page_result
        
        self.stats['cache_misses'] += 1
        logger.debug(f"Промах кэша, вычисление нового результата для пользователя {user_id}")
        start_time = time.time()
        
        result = compute_func()
        computation_time = (time.time() - start_time) * 1000
        
        ttl = self._get_adaptive_ttl(query_complexity, computation_time)
        
        self._set_cached_result(page_cache_key, result, ttl=ttl, user_id=user_id)
        
        if computation_time > 100:
            self._set_cached_result(base_cache_key, result, ttl=ttl * 2, user_id=user_id)
        
        logger.info(f"Вычислена и закэширована лента для пользователя {user_id} за {computation_time:.1f}мс")
        
        return result
    
    def get_or_compute_feed_overview(
        self,
        compute_func,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Получает обзор ленты с более длительным кэшированием, так как он меняется реже."""
        cache_key = self._build_overview_cache_key(user_id, filters, pagination)
        
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            self.stats['cache_hits'] += 1
            logger.debug(f"Попадание в кэш обзора для пользователя {user_id}")
            return cached_result
        
        self.stats['cache_misses'] += 1
        start_time = time.time()
        result = compute_func()
        computation_time = (time.time() - start_time) * 1000
        
        self._set_cached_result(cache_key, result, ttl=self.cache_ttl_overview, user_id=user_id)
        
        logger.info(f"Вычислен обзор для пользователя {user_id} за {computation_time:.1f}мс")
        
        return result
    
    def invalidate_user_feed_cache(self, user_id: int, partial: bool = False):
        """
        Инвалидирует кэш ленты для пользователя используя реестр ключей.
        
        Args:
            user_id: ID пользователя для инвалидации кэша
            partial: Если True, инвалидирует только комплексные ленты, сохраняет обзоры
        """
        try:
            keys_cleaned = self.key_registry.cleanup_user_cache(user_id)
            
            if keys_cleaned > 0:
                logger.info(f"Инвалидировано {keys_cleaned} записей кэша для пользователя {user_id}")
            else:
                logger.debug(f"Записи кэша для пользователя {user_id} не найдены")
        except Exception as e:
            logger.error(f"Не удалось инвалидировать кэш пользователя {user_id}: {e}")
            if partial:
                pattern = f"comprehensive_feed:*user_id*{user_id}*include_signals*true*"
            else:
                pattern = f"*feed*user_id*{user_id}*"
            
            self._invalidate_cache_pattern(pattern)
    
    def warm_feed_cache(self, user_id: int, common_filters: List[Dict[str, Any]]):
        """Предварительно прогревает кэш ленты с распространенными комбинациями фильтров."""
        if not self.memory_monitor.should_cache():
            logger.warning(f"Пропуск прогрева кэша для пользователя {user_id} из-за нехватки памяти")
            return
        
        for filters in common_filters:
            cache_key = self._build_base_cache_key(user_id, filters, include_signals=False)
            if not cache.get(cache_key):
                pass
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получает комплексную статистику кэша."""
        memory_stats = self.memory_monitor.get_memory_stats()
        registry_stats = self.key_registry.get_registry_stats()
        
        return {
            'cache_performance': self.stats.copy(),
            'memory_status': memory_stats,
            'key_registry': registry_stats,
            'cache_health': self._get_cache_health_status()
        }
    
    def _get_cache_health_status(self) -> str:
        """Получает общий статус здоровья кэша."""
        memory_stats = self.memory_monitor.get_memory_stats()
        
        if 'error' in memory_stats:
            return 'ERROR'
        
        memory_percent = memory_stats.get('memory_percent', 0)
        
        if memory_percent > self.memory_monitor.emergency_percent:
            return 'CRITICAL'
        elif memory_percent > self.memory_monitor.max_memory_percent:
            return 'WARNING'
        elif self.stats['memory_rejections'] > 0 or self.stats['size_rejections'] > 0:
            return 'DEGRADED'
        else:
            return 'HEALTHY'
    
    def cleanup_old_cache_entries(self, max_age_seconds: int = 3600):
        """Очищает старые записи кэша для освобождения памяти."""
        try:
            keys_cleaned = self.key_registry.cleanup_old_keys(max_age_seconds)
            if keys_cleaned > 0:
                logger.info(f"Очищено {keys_cleaned} старых записей кэша")
            return keys_cleaned
        except Exception as e:
            logger.error(f"Не удалось очистить старые записи кэша: {e}")
            return 0
    
    def _build_page_cache_key(
        self, 
        user_id: int, 
        filters: Optional[Dict], 
        pagination: Optional[Dict], 
        include_signals: bool,
        display_preference: Optional[str] = None,
        bypass_personal_filters: bool = True
    ) -> str:
        """Создает ключ кэша для конкретной страницы."""
        key_data = {
            'type': 'comprehensive_page',
            'user_id': user_id,
            'filters': filters or {},
            'pagination': pagination or {},
            'include_signals': include_signals,
            'display_preference': display_preference or 'ALL',
            'bypass_personal_filters': bypass_personal_filters,
            'version': 'v5'
        }
        return self._hash_cache_key(key_data)
    
    def _build_base_cache_key(
        self, 
        user_id: int, 
        filters: Optional[Dict], 
        include_signals: bool,
        display_preference: Optional[str] = None,
        bypass_personal_filters: bool = True
    ) -> str:
        """Создает ключ кэша для базового запроса (без пагинации)."""
        key_data = {
            'type': 'comprehensive_base',
            'user_id': user_id,
            'filters': filters or {},
            'include_signals': include_signals,
            'display_preference': display_preference or 'ALL',
            'bypass_personal_filters': bypass_personal_filters,
            'version': 'v5'
        }
        return self._hash_cache_key(key_data)
    
    def _build_overview_cache_key(
        self, 
        user_id: int, 
        filters: Optional[Dict], 
        pagination: Optional[Dict]
    ) -> str:
        """Создает ключ кэша для запросов обзора."""
        key_data = {
            'type': 'feed_overview',
            'user_id': user_id,
            'filters': filters or {},
            'pagination': pagination or {},
            'version': 'v3'
        }
        return self._hash_cache_key(key_data)
    
    def _hash_cache_key(self, key_data: Dict[str, Any]) -> str:
        """Создает хэш из данных ключа кэша."""
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_json.encode('utf-8')).hexdigest()
        return f"feed_cache:{key_hash}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Получает закэшированный результат с автоматической проверкой устаревания."""
        cached_data = cache.get(cache_key)
        if cached_data is None:
            return None
        
        if isinstance(cached_data, dict) and 'timestamp' in cached_data:
            cache_age = time.time() - cached_data['timestamp']
            max_age = cached_data.get('max_age', self.cache_ttl_comprehensive)
            
            if cache_age > max_age:
                cache.delete(cache_key)
                return None
        
        return cached_data.get('result') if isinstance(cached_data, dict) else cached_data
    
    def _set_cached_result(self, cache_key: str, result: Any, ttl: int, user_id: Optional[int] = None) -> bool:
        """
        Устанавливает закэшированный результат с проверками безопасности памяти и метаданными.
        
        Args:
            cache_key: Ключ кэша для хранения
            result: Данные результата для кэширования
            ttl: Время жизни в секундах
            user_id: Опциональный ID пользователя для отслеживания
            
        Returns:
            bool: True если успешно закэшировано, False если отклонено из соображений безопасности
        """
        try:
            estimated_size = self.memory_monitor.estimate_data_size(result)
            
            if not self.memory_monitor.should_cache(estimated_size):
                if estimated_size > self.memory_monitor.max_entry_size_bytes:
                    self.stats['size_rejections'] += 1
                    logger.warning(f"Кэш отклонен: Запись слишком большая ({estimated_size / 1024 / 1024:.1f}MB)")
                else:
                    self.stats['memory_rejections'] += 1
                    logger.warning(f"Кэш отклонен: Обнаружена нехватка памяти")
                return False
            
            cached_data = {
                'result': result,
                'timestamp': time.time(),
                'max_age': ttl,
                'cached_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'size_bytes': estimated_size,
                'user_id': user_id
            }
            
            cache.set(cache_key, cached_data, ttl)
            self.stats['cache_sets'] += 1
            
            self.key_registry.register_cache_key(
                cache_key=cache_key,
                user_id=user_id,
                metadata={
                    'size_bytes': estimated_size,
                    'ttl': ttl,
                    'type': 'comprehensive_feed'
                }
            )
            
            logger.debug(f"Результат закэширован: {cache_key[:50]}... ({estimated_size / 1024:.1f}KB)")
            return True
            
        except Exception as e:
            logger.error(f"Не удалось закэшировать результат {cache_key[:50]}...: {e}")
            return False
    
    def _get_adaptive_ttl(self, query_complexity: str, computation_time: float) -> int:
        """Получает адаптивный TTL на основе сложности запроса и времени вычисления."""
        base_ttl = self.cache_ttl_comprehensive
        
        if computation_time > 500:
            multiplier = 2.0
        elif computation_time > 200:
            multiplier = 1.5
        else:
            multiplier = 1.0
        
        if query_complexity == 'comprehensive':
            multiplier *= 1.5
        
        return int(base_ttl * multiplier)
    
    def _can_extract_page_from_base(self, base_result: Any, pagination: Optional[Dict]) -> bool:
        """Проверяет, можно ли извлечь запрошенную страницу из базового закэшированного результата."""
        if not pagination or not hasattr(base_result, 'nodes'):
            return False
        
        if not (hasattr(base_result, 'total_count') and hasattr(base_result, 'nodes')):
            return False
        
        page = pagination.get('page', 1)
        page_size = pagination.get('page_size', 20)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        available_nodes = len(base_result.nodes)
        
        if available_nodes < end_index and page > 1:
            return False
        
        if page > 10:
            return False
        
        if hasattr(base_result, 'total_count') and base_result.total_count is not None:
            max_possible_page = (base_result.total_count + page_size - 1) // page_size
            if page > max_possible_page:
                return False
        
        return True
    
    def _extract_page_from_base(self, base_result: Any, pagination: Optional[Dict]) -> Any:
        """Извлекает конкретную страницу из базового закэшированного результата."""
        if not pagination:
            return base_result
        
        page = pagination.get('page', 1)
        page_size = pagination.get('page_size', 20)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        page_nodes = base_result.nodes[start_index:end_index]
        total_count = getattr(base_result, 'total_count', len(base_result.nodes))
        total_pages = (total_count + page_size - 1) // page_size
        has_next_page = page < total_pages
        
        return SimpleNamespace(
            nodes=page_nodes,
            total_count=total_count,
            has_next_page=has_next_page,
            current_page=page,
            total_pages=total_pages
        )
    
    def _invalidate_cache_pattern(self, pattern: str) -> None:
        """Инвалидирует записи кэша, соответствующие паттерну."""
        try:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)
            else:
                logger.warning(f"Бэкенд кэша не поддерживает удаление по паттерну. Паттерн: {pattern}")
                
                if 'user_id' in pattern:
                    user_match = re.search(r'user_id\*(\d+)', pattern)
                    if user_match:
                        user_id = user_match.group(1)
                        logger.info(f"Очистка всего кэша ленты GraphQL для пользователя {user_id}")
                        cache.clear()
                else:
                    logger.warning("Не удалось определить ID пользователя из паттерна, очистка всего кэша")
                    cache.clear()
        except Exception as e:
            logger.error(f"Ошибка при инвалидации паттерна кэша {pattern}: {e}")
            try:
                cache.clear()
                logger.warning("Очищен весь кэш из-за ошибки инвалидации")
            except Exception as clear_error:
                logger.error(f"Не удалось очистить кэш: {clear_error}")


comprehensive_cache_manager = ComprehensiveFeedCacheManager()


def get_comprehensive_cache_manager() -> ComprehensiveFeedCacheManager:
    """Получает глобальный менеджер кэша комплексных лент."""
    return comprehensive_cache_manager
