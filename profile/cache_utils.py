"""
Cache utilities that work with both Redis and local memory cache backends.
"""
from django.core.cache import cache
from django.conf import settings
import fnmatch


def safe_delete_pattern(pattern):
    """
    Safely delete cache keys matching a pattern.
    Works with both Redis and local memory cache.
    
    Args:
        pattern (str): Cache key pattern to match (with wildcards like *)
    """
    try:
        # Try Redis-specific delete_pattern first
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
            return True
    except AttributeError:
        pass
    
    # Fallback for local memory cache and other backends
    # This is less efficient but works with any cache backend
    try:
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'keys'):
            # For LocMemCache, we can access the internal cache dict
            all_keys = list(cache._cache.keys())
            matching_keys = [key for key in all_keys if fnmatch.fnmatch(key, pattern)]
            if matching_keys:
                cache.delete_many(matching_keys)
                return True
        elif hasattr(cache, 'keys') and callable(cache.keys):
            # For backends that support keys() method
            try:
                all_keys = cache.keys('*')
                matching_keys = [key for key in all_keys if fnmatch.fnmatch(key, pattern)]
                if matching_keys:
                    cache.delete_many(matching_keys)
                    return True
            except:
                pass
    except:
        pass
    
    # If pattern deletion is not supported, just log and continue
    # This ensures the application doesn't crash
    print(f"Warning: Pattern deletion not supported for pattern: {pattern}")
    return False


def safe_cache_set(key, value, timeout=None):
    """
    Safely set a cache value with error handling.
    
    Args:
        key (str): Cache key
        value: Value to cache
        timeout (int, optional): Cache timeout in seconds
    """
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as e:
        print(f"Warning: Failed to set cache key {key}: {e}")
        return False


def safe_cache_get(key, default=None):
    """
    Safely get a cache value with error handling.
    
    Args:
        key (str): Cache key
        default: Default value if key not found or error occurs
    
    Returns:
        Cached value or default
    """
    try:
        return cache.get(key, default)
    except Exception as e:
        print(f"Warning: Failed to get cache key {key}: {e}")
        return default


def safe_cache_delete(key):
    """
    Safely delete a cache key with error handling.
    
    Args:
        key (str): Cache key to delete
    """
    try:
        cache.delete(key)
        return True
    except Exception as e:
        print(f"Warning: Failed to delete cache key {key}: {e}")
        return False 