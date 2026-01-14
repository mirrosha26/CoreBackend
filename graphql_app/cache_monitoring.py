"""
Система мониторинга памяти кэша для предотвращения падений сервера.
"""

import logging
import pickle
import sys
import threading
import time
from typing import Any, Dict, Optional, Set

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil недоступен - мониторинг памяти отключен")


class CacheMemoryMonitor:
    """Мониторинг использования памяти кэша и предотвращение переполнения памяти."""
    
    def __init__(self):
        self.max_memory_percent = getattr(settings, 'CACHE_MEMORY_THRESHOLD_PERCENT', 85)
        self.emergency_percent = getattr(settings, 'CACHE_EMERGENCY_CLEANUP_PERCENT', 90)
        self.max_entry_size_mb = getattr(settings, 'CACHE_MAX_ENTRY_SIZE_MB', 1)
        self.max_entry_size_bytes = self.max_entry_size_mb * 1024 * 1024
        
        self.stats = {
            'memory_checks': 0,
            'cache_rejections': 0,
            'emergency_cleanups': 0,
            'oversized_rejections': 0,
            'last_cleanup': None
        }
        
        self._last_cleanup_time = 0
        self._cleanup_interval = 60
        
    def should_cache(self, data_size_bytes: Optional[int] = None) -> bool:
        """Проверяет, безопасно ли добавлять новые записи в кэш."""
        self.stats['memory_checks'] += 1
        
        try:
            if PSUTIL_AVAILABLE:
                memory = psutil.virtual_memory()
                
                if memory.percent > self.max_memory_percent:
                    logger.warning(
                        f"Кэш отклонен: Использование памяти {memory.percent:.1f}% превышает "
                        f"порог {self.max_memory_percent}%"
                    )
                    self.stats['cache_rejections'] += 1
                    
                    if memory.percent > self.emergency_percent:
                        self._emergency_cleanup()
                    
                    return False
            
            if data_size_bytes and data_size_bytes > self.max_entry_size_bytes:
                logger.warning(
                    f"Кэш отклонен: Размер записи {data_size_bytes / 1024 / 1024:.1f}MB "
                    f"превышает лимит {self.max_entry_size_mb}MB"
                )
                self.stats['oversized_rejections'] += 1
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке безопасности кэша: {e}")
            return False
    
    def estimate_data_size(self, data: Any) -> int:
        """Оценивает размер данных в памяти в байтах."""
        try:
            return len(pickle.dumps(data))
        except Exception as e:
            logger.warning(f"Не удалось оценить размер данных: {e}")
            return sys.getsizeof(data)
    
    def _emergency_cleanup(self):
        """Выполняет экстренную очистку кэша для освобождения памяти."""
        current_time = time.time()
        
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        self._last_cleanup_time = current_time
        self.stats['emergency_cleanups'] += 1
        self.stats['last_cleanup'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            logger.warning("Выполняется экстренная очистка кэша из-за высокого использования памяти")
            cache.clear()
            logger.info("Экстренная очистка кэша завершена")
        except Exception as e:
            logger.error(f"Экстренная очистка кэша не удалась: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Получает текущую статистику памяти и кэша."""
        try:
            base_stats = {
                'cache_monitor_stats': self.stats.copy(),
                'thresholds': {
                    'warning_percent': self.max_memory_percent,
                    'emergency_percent': self.emergency_percent,
                    'max_entry_size_mb': self.max_entry_size_mb
                }
            }
            
            if PSUTIL_AVAILABLE:
                memory = psutil.virtual_memory()
                base_stats.update({
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_total_gb': memory.total / (1024**3),
                })
            else:
                base_stats.update({
                    'memory_percent': 0,
                    'memory_available_gb': 0,
                    'memory_used_gb': 0,
                    'memory_total_gb': 0,
                    'psutil_unavailable': True
                })
            
            return base_stats
        except Exception as e:
            logger.error(f"Не удалось получить статистику памяти: {e}")
            return {'error': str(e)}
    
    def log_memory_status(self):
        """Логирует текущий статус памяти для мониторинга."""
        stats = self.get_memory_stats()
        
        if 'error' in stats:
            return
        
        memory_percent = stats['memory_percent']
        
        if memory_percent > self.emergency_percent:
            log_level, status = logger.error, "CRITICAL"
        elif memory_percent > self.max_memory_percent:
            log_level, status = logger.warning, "WARNING"
        else:
            log_level, status = logger.info, "OK"
        
        log_level(
            f"Cache Memory Status: {status} - "
            f"Memory: {memory_percent:.1f}% "
            f"({stats['memory_used_gb']:.1f}GB used / {stats['memory_total_gb']:.1f}GB total)"
        )


class CacheKeyRegistry:
    """Отслеживает и управляет ключами кэша для правильной очистки."""
    
    def __init__(self):
        self.user_cache_keys: Dict[int, Set[str]] = {}
        self.cache_key_metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def register_cache_key(self, cache_key: str, user_id: Optional[int] = None, 
                          metadata: Optional[Dict[str, Any]] = None):
        """Регистрирует ключ кэша для отслеживания."""
        with self._lock:
            if user_id:
                self.user_cache_keys.setdefault(user_id, set()).add(cache_key)
            
            if metadata:
                self.cache_key_metadata[cache_key] = {
                    'created_at': time.time(),
                    'user_id': user_id,
                    **metadata
                }
    
    def cleanup_user_cache(self, user_id: int) -> int:
        """Очищает все ключи кэша для конкретного пользователя."""
        with self._lock:
            if user_id not in self.user_cache_keys:
                return 0
            
            keys_to_delete = list(self.user_cache_keys[user_id])
            
            if not keys_to_delete:
                return 0
            
            try:
                cache.delete_many(keys_to_delete)
                
                for key in keys_to_delete:
                    self.cache_key_metadata.pop(key, None)
                
                del self.user_cache_keys[user_id]
                
                logger.info(f"Очищено {len(keys_to_delete)} записей кэша для пользователя {user_id}")
                return len(keys_to_delete)
            except Exception as e:
                logger.error(f"Не удалось очистить кэш пользователя {user_id}: {e}")
                return 0
    
    def cleanup_old_keys(self, max_age_seconds: int = 3600) -> int:
        """Очищает ключи кэша старше указанного возраста."""
        with self._lock:
            current_time = time.time()
            old_keys = [
                key for key, metadata in self.cache_key_metadata.items()
                if current_time - metadata.get('created_at', current_time) > max_age_seconds
            ]
            
            if not old_keys:
                return 0
            
            try:
                cache.delete_many(old_keys)
                
                for key in old_keys:
                    metadata = self.cache_key_metadata.pop(key, {})
                    user_id = metadata.get('user_id')
                    
                    if user_id and user_id in self.user_cache_keys:
                        self.user_cache_keys[user_id].discard(key)
                        if not self.user_cache_keys[user_id]:
                            del self.user_cache_keys[user_id]
                
                logger.info(f"Очищено {len(old_keys)} старых записей кэша")
                return len(old_keys)
            except Exception as e:
                logger.error(f"Не удалось очистить старые ключи кэша: {e}")
                return 0
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Получает статистику реестра ключей кэша."""
        with self._lock:
            total_user_keys = sum(len(keys) for keys in self.user_cache_keys.values())
            users_count = len(self.user_cache_keys)
            
            return {
                'total_tracked_keys': len(self.cache_key_metadata),
                'users_with_cache': users_count,
                'total_user_keys': total_user_keys,
                'average_keys_per_user': total_user_keys / users_count if users_count else 0
            }


cache_memory_monitor = CacheMemoryMonitor()
cache_key_registry = CacheKeyRegistry()


def get_cache_memory_monitor() -> CacheMemoryMonitor:
    """Получает глобальный монитор памяти кэша."""
    return cache_memory_monitor


def get_cache_key_registry() -> CacheKeyRegistry:
    """Получает глобальный реестр ключей кэша."""
    return cache_key_registry


def log_cache_health_status():
    """Логирует статус здоровья кэша."""
    try:
        monitor = get_cache_memory_monitor()
        registry = get_cache_key_registry()
        
        memory_stats = monitor.get_memory_stats()
        registry_stats = registry.get_registry_stats()
        
        memory_percent = memory_stats.get('memory_percent', 0)
        
        if memory_percent > monitor.emergency_percent:
            logger.critical(
                f"🚨 КРИТИЧНО: Использование памяти {memory_percent:.1f}% - Требуется экстренная очистка!"
            )
        elif memory_percent > monitor.max_memory_percent:
            logger.warning(
                f"⚠️ ВНИМАНИЕ: Использование памяти {memory_percent:.1f}% - Следите внимательно"
            )
        else:
            logger.info(
                f"✅ Кэш в порядке: Память {memory_percent:.1f}%, "
                f"{registry_stats['total_tracked_keys']} записей в кэше"
            )
    except Exception as e:
        logger.error(f"Не удалось проверить здоровье кэша: {e}")
