from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone

from .models import (
    TeamMember,
    SourceType,
    Source,
    SignalType,
    Category,
    SignalCard,
    Signal,
    Participant,
    SignalRaw,
    STAGES,
    ROUNDS
)
from .serializers import (
    TeamMemberSerializer,
    SourceTypeSerializer,
    SourceSerializer,
    SignalTypeSerializer,
    CategorySerializer,
    SignalCardSerializer,
    SignalSerializer,
    ParticipantSerializer,
    SignalRawSerializer
)
from .filters import (
    ParticipantFilter, 
    SourceFilter, 
    SignalFilter,
    SignalCardFilter
)
from .permissions import IsAdminUserWithToken


class SourceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet только для чтения типов источников данных.
    
    Предоставляет список типов источников (Twitter, LinkedIn и т.д.).
    """
    queryset = SourceType.objects.all()
    serializer_class = SourceTypeSerializer
    permission_classes = [IsAdminUserWithToken]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['id', 'name']
    ordering = ['name']


class SourceViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для источников данных из социальных сетей.
    
    Управление профилями участников в различных социальных сетях.
    """
    queryset = Source.objects.select_related('source_type', 'participant')
    serializer_class = SourceSerializer
    permission_classes = [IsAdminUserWithToken]
    filterset_class = SourceFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['slug', 'participant__name', 'social_network_id']
    ordering_fields = ['id', 'slug']
    ordering = ['id']


class SignalTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet только для чтения типов сигналов.
    
    Предоставляет список типов сигналов (инвестиция, партнёрство и т.д.).
    """
    queryset = SignalType.objects.all()
    serializer_class = SignalTypeSerializer
    permission_classes = [IsAdminUserWithToken]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['id', 'name']
    ordering = ['name']


class CategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для категорий проектов.
    
    Управление категориями для классификации проектов.
    """
    queryset = Category.objects.select_related('parent_category')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserWithToken]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['id', 'name']
    ordering = ['name']


class SignalCardViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для карточек проектов (SignalCard).
    
    Управление проектами с их категориями, стадиями развития и раундами.
    """
    queryset = SignalCard.objects.prefetch_related('categories', 'signals')
    serializer_class = SignalCardSerializer
    permission_classes = [IsAdminUserWithToken]
    filterset_class = SignalCardFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug', 'description']
    ordering_fields = ['id', 'created_at', 'updated_at', 'name']
    ordering = ['-created_at']


class SignalViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для сигналов (событий от участников).
    
    Управление событиями, связывающими участников с проектами.
    """
    queryset = Signal.objects.select_related(
        'signal_card', 
        'participant', 
        'associated_participant',
        'source', 
        'signal_type'
    )
    serializer_class = SignalSerializer
    permission_classes = [IsAdminUserWithToken]
    filterset_class = SignalFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering_fields = ['id', 'created_at']
    ordering = ['-created_at']


class TeamMemberViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для членов команды проектов.
    
    Управление информацией о членах команд проектов.
    """
    queryset = TeamMember.objects.select_related('signal_card')
    serializer_class = TeamMemberSerializer
    permission_classes = [IsAdminUserWithToken]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'headline']
    ordering_fields = ['id', 'name']
    ordering = ['name']


class ParticipantViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet для участников (инвесторы, фонды, компании).
    
    Управление участниками экосистемы и их активностью.
    """
    queryset = Participant.objects.select_related('associated_with')
    serializer_class = ParticipantSerializer
    permission_classes = [IsAdminUserWithToken]
    filterset_class = ParticipantFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug', 'about']
    ordering_fields = ['id', 'name', 'monthly_signals_count']
    ordering = ['-monthly_signals_count']


class SignalRawViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset для сырых данных сигналов от микросервиса.
    
    Микросервис сбора данных отправляет сюда необработанные данные,
    которые затем обрабатываются и преобразуются в Signal и SignalCard.
    """
    queryset = SignalRaw.objects.all().select_related(
        'source', 'signal_type', 'signal_card', 'signal'
    )
    serializer_class = SignalRawSerializer
    permission_classes = [IsAdminUserWithToken]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'is_processed', 'source', 'signal_type', 
        'category', 'stage', 'round'
    ]
    search_fields = [
        'source__slug', 'description', 
        'label', 'website', 'category', 'stage', 'round'
    ]
    ordering_fields = ['id', 'created_at', 'processed_at', 'updated_at']
    ordering = ['-created_at']


@api_view(['GET'])
@permission_classes([IsAdminUserWithToken])
def get_stages(request):
    """
    Получить список всех доступных стадий развития проектов.
    
    Returns:
        Response: Массив объектов со slug и name каждой стадии
        
    Example:
        [
            {"slug": "idea", "name": "Idea"},
            {"slug": "mvp", "name": "MVP"},
            ...
        ]
    """
    stages_array = [
        {
            'slug': stage[0],
            'name': stage[1]
        }
        for stage in STAGES
    ]
    return Response(stages_array)


@api_view(['GET'])
@permission_classes([IsAdminUserWithToken])
def get_rounds(request):
    """
    Получить список всех доступных раундов финансирования.
    
    Returns:
        Response: Массив объектов со slug и name каждого раунда
        
    Example:
        [
            {"slug": "pre-seed", "name": "Pre-Seed"},
            {"slug": "seed", "name": "Seed"},
            ...
        ]
    """
    rounds_array = [
        {
            'slug': round_item[0],
            'name': round_item[1]
        }
        for round_item in ROUNDS
    ]
    return Response(rounds_array)
