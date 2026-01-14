"""
Расширенная система prefetch для GraphQL запросов.

Модуль анализирует структуру GraphQL запросов и применяет оптимальные стратегии prefetch
на основе запрошенных полей для минимизации запросов к БД.
"""

import logging
from typing import Set

from django.db.models import Prefetch, Q, QuerySet

from signals.models import SignalCard, Signal

logger = logging.getLogger(__name__)


class GraphQLQueryAnalyzer:
    """Анализирует GraphQL запросы для определения оптимальных стратегий prefetch."""
    
    def __init__(self, info):
        self.info = info
        self.selected_fields = self._extract_selected_fields()
        self.query_type = self._determine_query_type()
        self.complexity_score = self._calculate_complexity()
    
    def _extract_selected_fields(self) -> Set[str]:
        """Извлекает все имена выбранных полей из GraphQL запроса."""
        selected_fields = set()
        
        def traverse_selection_set(selection_set, path=""):
            if not selection_set:
                return
            
            for selection in selection_set.selections:
                if hasattr(selection, 'name'):
                    field_name = selection.name.value
                    full_path = f"{path}.{field_name}" if path else field_name
                    selected_fields.add(full_path)
                    
                    if hasattr(selection, 'selection_set') and selection.selection_set:
                        traverse_selection_set(selection.selection_set, full_path)
        
        if hasattr(self.info, 'field_nodes') and self.info.field_nodes:
            for field_node in self.info.field_nodes:
                if hasattr(field_node, 'selection_set') and field_node.selection_set:
                    traverse_selection_set(field_node.selection_set)
        
        return selected_fields
    
    def _determine_query_type(self) -> str:
        """Определяет тип запроса на основе выбранных полей."""
        if self.has_signals() and self.has_participants() and self.has_categories():
            return "comprehensive"
        elif self.has_signals():
            return "signals_heavy"
        elif self.has_participants():
            return "participants_heavy"
        else:
            return "lightweight"
    
    def _calculate_complexity(self) -> int:
        """Вычисляет оценку сложности запроса."""
        complexity = len(self.selected_fields)
        
        if self.has_signals():
            complexity += 10
        if self.has_participants():
            complexity += 8
        if self.has_categories():
            complexity += 3
        if self.has_user_data():
            complexity += 5
        if self.has_social_links():
            complexity += 2
        if self.has_nested_participants_in_signals():
            complexity += 15
        
        return complexity
    
    def has_signals(self) -> bool:
        """Проверяет, запрашивает ли запрос сигналы."""
        return any('signals' in field for field in self.selected_fields)
    
    def has_participants(self) -> bool:
        """Проверяет, запрашивает ли запрос участников."""
        return any('participant' in field for field in self.selected_fields)
    
    def has_categories(self) -> bool:
        """Проверяет, запрашивает ли запрос категории."""
        return any('categories' in field for field in self.selected_fields)
    
    def has_user_data(self) -> bool:
        """Проверяет, запрашивает ли запрос пользовательские данные."""
        return any('userData' in field for field in self.selected_fields)
    
    def has_social_links(self) -> bool:
        """Проверяет, запрашивает ли запрос социальные ссылки."""
        return any('socialLinks' in field for field in self.selected_fields)
    
    def has_nested_participants_in_signals(self) -> bool:
        """Проверяет, запрашивает ли запрос участников внутри сигналов."""
        return any('signals.participant' in field or 'signals.associatedParticipant' in field 
                  for field in self.selected_fields)
    
    def is_comprehensive_query(self) -> bool:
        """Проверяет, является ли это комплексным запросом, требующим специальной оптимизации."""
        return (self.query_type == "comprehensive" or 
                self.complexity_score > 20 or
                self.has_nested_participants_in_signals())


class EnhancedPrefetchStrategy:
    """Применяет расширенный prefetch на основе анализа запроса."""
    
    def __init__(self, analyzer: GraphQLQueryAnalyzer, user=None):
        self.analyzer = analyzer
        self.user = user
    
    def apply_prefetch_optimizations(self, queryset: QuerySet) -> QuerySet:
        """Применяет оптимизации prefetch на основе анализа запроса."""
        if self.analyzer.is_comprehensive_query():
            return self._apply_comprehensive_prefetch(queryset)
        elif self.analyzer.query_type == "signals_heavy":
            return self._apply_signals_heavy_prefetch(queryset)
        elif self.analyzer.query_type == "participants_heavy":
            return self._apply_participants_heavy_prefetch(queryset)
        else:
            return self._apply_lightweight_prefetch(queryset)
    
    def _apply_comprehensive_prefetch(self, queryset: QuerySet) -> QuerySet:
        """Применяет комплексный prefetch для сложных запросов."""
        prefetches = []
        
        if self.analyzer.has_categories():
            prefetches.append('categories')
        
        if self.analyzer.has_signals():
            privacy_filter = self._build_privacy_filter()
            
            signals_prefetch = Prefetch(
                'signals',
                queryset=Signal.objects.filter(privacy_filter).select_related(
                    'participant',
                    'associated_participant',
                    'signal_type'
                ).order_by('-created_at'),
                to_attr='prefetched_signals'
            )
            prefetches.append(signals_prefetch)
        
        if prefetches:
            queryset = queryset.prefetch_related(*prefetches)
        
        return queryset
    
    def _apply_signals_heavy_prefetch(self, queryset: QuerySet) -> QuerySet:
        """Применяет оптимизации для запросов с большим количеством сигналов."""
        privacy_filter = self._build_privacy_filter()
        
        signals_prefetch = Prefetch(
            'signals',
            queryset=Signal.objects.filter(privacy_filter).select_related(
                'participant',
                'associated_participant'
            ).order_by('-created_at')[:50],
            to_attr='prefetched_signals'
        )
        
        return queryset.prefetch_related(signals_prefetch)
    
    def _apply_participants_heavy_prefetch(self, queryset: QuerySet) -> QuerySet:
        """Применяет оптимизации для запросов с большим количеством участников."""
        return queryset.prefetch_related('categories')
    
    def _apply_lightweight_prefetch(self, queryset: QuerySet) -> QuerySet:
        """Применяет минимальный prefetch для легких запросов."""
        if self.analyzer.has_categories():
            queryset = queryset.prefetch_related('categories')
        
        return queryset
    
    def _build_privacy_filter(self) -> Q:
        """Создает фильтр для prefetch сигналов - все сигналы доступны."""
        return Q(
            Q(participant__isnull=False) | Q(associated_participant__isnull=False)
        )


def create_optimized_queryset(base_queryset: QuerySet, info, user=None) -> QuerySet:
    """
    Создает оптимизированный queryset на основе анализа GraphQL запроса.
    
    Args:
        base_queryset: Базовый SignalCard queryset
        info: GraphQL resolve info
        user: Текущий пользователь для фильтрации приватности
    
    Returns:
        Оптимизированный queryset с соответствующим prefetch
    """
    analyzer = GraphQLQueryAnalyzer(info)
    strategy = EnhancedPrefetchStrategy(analyzer, user)
    return strategy.apply_prefetch_optimizations(base_queryset)
