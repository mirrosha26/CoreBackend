"""
Мониторинг производительности и инструменты оптимизации для GraphQL запросов.
"""

import logging
import time
from functools import wraps
from typing import Any, Dict

from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """Мониторит и анализирует производительность GraphQL запросов."""
    
    def __init__(self):
        self.query_stats = {}
    
    def start_monitoring(self, query_name: str, user_id: int = None) -> str:
        """Начинает мониторинг запроса."""
        monitor_id = f"{query_name}_{user_id}_{int(time.time() * 1000)}"
        self.query_stats[monitor_id] = {
            'query_name': query_name,
            'user_id': user_id,
            'start_time': time.time(),
            'initial_query_count': len(connection.queries),
            'cache_hits': 0,
            'cache_misses': 0,
        }
        return monitor_id
    
    def end_monitoring(self, monitor_id: str) -> Dict[str, Any]:
        """Завершает мониторинг и возвращает статистику производительности."""
        if monitor_id not in self.query_stats:
            return {}
        
        stats = self.query_stats[monitor_id]
        end_time = time.time()
        
        performance_data = {
            'query_name': stats['query_name'],
            'user_id': stats['user_id'],
            'execution_time_ms': (end_time - stats['start_time']) * 1000,
            'database_queries': len(connection.queries) - stats['initial_query_count'],
            'cache_hits': stats['cache_hits'],
            'cache_misses': stats['cache_misses'],
        }
        
        if settings.DEBUG:
            self._log_performance(performance_data)
        
        del self.query_stats[monitor_id]
        
        return performance_data
    
    def record_cache_hit(self, monitor_id: str):
        """Записывает попадание в кэш."""
        if monitor_id in self.query_stats:
            self.query_stats[monitor_id]['cache_hits'] += 1
    
    def record_cache_miss(self, monitor_id: str):
        """Записывает промах кэша."""
        if monitor_id in self.query_stats:
            self.query_stats[monitor_id]['cache_misses'] += 1
    
    def _log_performance(self, data: Dict[str, Any]):
        """Логирует данные о производительности."""
        query_name = data['query_name']
        exec_time = data['execution_time_ms']
        db_queries = data['database_queries']
        
        if exec_time > 1000:
            logger.warning(
                f"МЕДЛЕННЫЙ ЗАПРОС: {query_name} занял {exec_time:.2f}мс "
                f"с {db_queries} запросами к БД"
            )
        elif exec_time > 500:
            logger.info(
                f"СРЕДНИЙ ЗАПРОС: {query_name} занял {exec_time:.2f}мс "
                f"с {db_queries} запросами к БД"
            )


performance_monitor = QueryPerformanceMonitor()


def monitor_query_performance(query_name: str):
    """Декоратор для мониторинга производительности GraphQL запросов."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = None
            for arg in args:
                if hasattr(arg, 'context'):
                    user = getattr(arg.context.get("request"), 'user', None)
                    break
            
            user_id = user.id if user and user.is_authenticated else None
            
            monitor_id = performance_monitor.start_monitoring(query_name, user_id)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                performance_data = performance_monitor.end_monitoring(monitor_id)
                
                if performance_data and user_id:
                    cache_key = f"query_perf:{query_name}:{user_id}"
                    cache.set(cache_key, performance_data, timeout=3600)
        
        return wrapper
    return decorator


class SmartCache:
    """Умное кэширование с отслеживанием производительности."""
    
    @staticmethod
    def get(key: str, monitor_id: str = None) -> Any:
        """Получает значение из кэша с отслеживанием производительности."""
        result = cache.get(key)
        
        if monitor_id:
            if result is not None:
                performance_monitor.record_cache_hit(monitor_id)
            else:
                performance_monitor.record_cache_miss(monitor_id)
        
        return result
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> None:
        """Устанавливает значение в кэш."""
        cache.set(key, value, timeout)
    
    @staticmethod
    def get_or_set(key: str, callable_func, timeout: int = 300, monitor_id: str = None) -> Any:
        """Получает значение из кэша или устанавливает, если не существует."""
        result = SmartCache.get(key, monitor_id)
        
        if result is None:
            result = callable_func()
            SmartCache.set(key, result, timeout)
        
        return result
