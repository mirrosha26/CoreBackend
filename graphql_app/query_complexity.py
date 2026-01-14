"""
Анализ сложности GraphQL запросов для оптимизации производительности.

Модуль предоставляет анализ сложности запросов для предотвращения дорогих запросов
и обеспечения стабильной производительности GraphQL API.
"""

import logging
from typing import Any, Dict, List

from django.conf import settings
from graphql import GraphQLError
from graphql.type import GraphQLResolveInfo

logger = logging.getLogger(__name__)

DEFAULT_MAX_COMPLEXITY = getattr(settings, 'GRAPHQL_MAX_COMPLEXITY', 1000)
DEFAULT_MAX_DEPTH = getattr(settings, 'GRAPHQL_MAX_DEPTH', 15)
DEFAULT_INTROSPECTION_COMPLEXITY = getattr(settings, 'GRAPHQL_INTROSPECTION_COMPLEXITY', 100)

FIELD_COMPLEXITY_MAP = {
    'signalCards': 10,
    'userFeed': 8,
    'participants': 6,
    'categories': 3,
    'savedFilters': 4,
    'stages': 1,
    'roundStatuses': 1,
    'nodes': 2,
    'edges': 2,
    'pageInfo': 1,
    'signals': 3,
    'teamMembers': 2,
    'userData': 2,
    'recentProjectsCount': 5,
    'latestSignalDate': 2,
    'signalsCount': 2,
    'uniqueParticipantsCount': 3,
    'signalCard': 5,
    'groupAssignments': 8,
    'defaultSavedFilter': 3,
    'savedFiltersSummary': 4,
}

ARGUMENT_MULTIPLIERS = {
    'includeSignals': 1.5,
    'includeRecentCounts': 2.0,
    'includeUserData': 1.3,
    'search': 1.2,
}

class QueryComplexityAnalyzer:
    """Анализирует сложность GraphQL запросов для предотвращения дорогих операций."""
    
    def __init__(self, max_complexity: int = DEFAULT_MAX_COMPLEXITY, max_depth: int = DEFAULT_MAX_DEPTH):
        self.max_complexity = max_complexity
        self.max_depth = max_depth
        self.complexity_map = FIELD_COMPLEXITY_MAP.copy()
        self.argument_multipliers = ARGUMENT_MULTIPLIERS.copy()
    
    def analyze_query(self, info: GraphQLResolveInfo) -> Dict[str, Any]:
        """
        Анализирует GraphQL запрос и возвращает метрики сложности.
        
        Args:
            info: GraphQL resolve info, содержащий детали запроса
            
        Returns:
            Словарь с результатами анализа сложности
        """
        try:
            document = getattr(info, 'operation', None)
            if not document and hasattr(info, 'field_nodes'):
                document = info.field_nodes[0] if info.field_nodes else None
            
            if not document:
                return {'complexity': 0, 'depth': 0, 'valid': True}
            
            complexity = self._calculate_complexity(document, info)
            depth = self._calculate_depth(document)
            
            is_valid = complexity <= self.max_complexity and depth <= self.max_depth
            
            analysis = {
                'complexity': complexity,
                'depth': depth,
                'max_complexity': self.max_complexity,
                'max_depth': self.max_depth,
                'valid': is_valid,
                'field_breakdown': self._get_field_breakdown(document),
                'expensive_fields': self._get_expensive_fields(document),
            }
            
            if complexity > self.max_complexity * 0.8:
                logger.warning(
                    f"Обнаружен сложный GraphQL запрос: "
                    f"сложность={complexity}, глубина={depth}, "
                    f"операция={info.operation.name if info.operation else 'неизвестно'}"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Ошибка анализа сложности запроса: {e}")
            return {'complexity': 0, 'depth': 0, 'valid': True, 'error': str(e)}
    
    def _calculate_complexity(self, node: Any, info: GraphQLResolveInfo, multiplier: float = 1.0) -> int:
        """Вычисляет оценку сложности для узла запроса."""
        if not node:
            return 0
        
        complexity = 0
        
        if hasattr(node, 'selections'):
            for selection in node.selections:
                if hasattr(selection, 'name'):
                    field_name = selection.name.value
                    field_complexity = self.complexity_map.get(field_name, 1)
                    
                    field_multiplier = self._get_argument_multiplier(selection)
                    page_multiplier = self._get_pagination_multiplier(selection)
                    
                    total_field_complexity = field_complexity * field_multiplier * page_multiplier * multiplier
                    nested_complexity = self._calculate_complexity(selection, info, multiplier)
                    
                    complexity += total_field_complexity + nested_complexity
                    
        elif hasattr(node, 'operation_type'):
            complexity += self._calculate_complexity(node.selection_set, info, multiplier)
            
        return int(complexity)
    
    def _calculate_depth(self, node: Any, current_depth: int = 0) -> int:
        """Вычисляет максимальную глубину запроса."""
        if not node or not hasattr(node, 'selections'):
            return current_depth
        
        max_depth = current_depth
        
        for selection in node.selections:
            if hasattr(selection, 'selection_set') and selection.selection_set:
                depth = self._calculate_depth(selection.selection_set, current_depth + 1)
                max_depth = max(max_depth, depth)
            else:
                max_depth = max(max_depth, current_depth + 1)
        
        return max_depth
    
    def _get_argument_multiplier(self, selection: Any) -> float:
        """Получает множитель сложности на основе аргументов поля."""
        if not hasattr(selection, 'arguments'):
            return 1.0
        
        multiplier = 1.0
        
        for arg in selection.arguments:
            if hasattr(arg, 'name'):
                arg_name = arg.name.value
                if arg_name in self.argument_multipliers:
                    if hasattr(arg, 'value') and hasattr(arg.value, 'value'):
                        if arg.value.value is True:
                            multiplier *= self.argument_multipliers[arg_name]
                    else:
                        multiplier *= 1.1
        
        return multiplier
    
    def _get_pagination_multiplier(self, selection: Any) -> float:
        """Получает множитель сложности на основе аргументов пагинации."""
        if not hasattr(selection, 'arguments'):
            return 1.0
        
        multiplier = 1.0
        
        for arg in selection.arguments:
            if hasattr(arg, 'name'):
                arg_name = arg.name.value
                
                if arg_name in ['pageSize', 'first', 'last'] and hasattr(arg, 'value'):
                    if hasattr(arg.value, 'value'):
                        page_size = arg.value.value
                        if isinstance(page_size, int):
                            multiplier *= max(1.0, page_size / 20.0)
        
        return multiplier
    
    def _get_field_breakdown(self, node: Any) -> Dict[str, int]:
        """Получает разбивку сложности по полям."""
        breakdown = {}
        
        if hasattr(node, 'selections'):
            for selection in node.selections:
                if hasattr(selection, 'name'):
                    field_name = selection.name.value
                    field_complexity = self.complexity_map.get(field_name, 1)
                    breakdown[field_name] = field_complexity
                    
                    nested_breakdown = self._get_field_breakdown(selection)
                    for nested_field, nested_complexity in nested_breakdown.items():
                        breakdown[f"{field_name}.{nested_field}"] = nested_complexity
        
        return breakdown
    
    def _get_expensive_fields(self, node: Any, threshold: int = 5) -> List[str]:
        """Получает список дорогих полей, превышающих порог сложности."""
        expensive_fields = []
        
        if hasattr(node, 'selections'):
            for selection in node.selections:
                if hasattr(selection, 'name'):
                    field_name = selection.name.value
                    field_complexity = self.complexity_map.get(field_name, 1)
                    
                    if field_complexity >= threshold:
                        expensive_fields.append(field_name)
                    
                    nested_expensive = self._get_expensive_fields(selection, threshold)
                    expensive_fields.extend([f"{field_name}.{field}" for field in nested_expensive])
        
        return expensive_fields
    
    def validate_query(self, info: GraphQLResolveInfo, raise_on_invalid: bool = True) -> bool:
        """
        Проверяет сложность запроса и вызывает ошибку, если запрос слишком сложный.
        
        Args:
            info: GraphQL resolve info
            raise_on_invalid: Вызывать ли GraphQLError для невалидных запросов
            
        Returns:
            True если запрос валиден, False в противном случае
        """
        analysis = self.analyze_query(info)
        
        if not analysis['valid']:
            error_message = (
                f"Сложность запроса слишком высока: {analysis['complexity']} "
                f"(макс: {self.max_complexity}), "
                f"глубина: {analysis['depth']} (макс: {self.max_depth})"
            )
            
            if raise_on_invalid:
                raise GraphQLError(error_message)
            else:
                logger.warning(f"Невалидная сложность запроса: {error_message}")
                return False
        
        return True


complexity_analyzer = QueryComplexityAnalyzer()


def analyze_query_complexity(info: GraphQLResolveInfo) -> Dict[str, Any]:
    """
    Анализирует сложность запроса для GraphQL операции.
    
    Args:
        info: GraphQL resolve info
        
    Returns:
        Словарь с результатами анализа сложности
    """
    return complexity_analyzer.analyze_query(info)


def validate_query_complexity(info: GraphQLResolveInfo, raise_on_invalid: bool = True) -> bool:
    """
    Проверяет сложность запроса и опционально вызывает ошибку.
    
    Args:
        info: GraphQL resolve info
        raise_on_invalid: Вызывать ли GraphQLError для невалидных запросов
        
    Returns:
        True если запрос валиден, False в противном случае
    """
    return complexity_analyzer.validate_query(info, raise_on_invalid)