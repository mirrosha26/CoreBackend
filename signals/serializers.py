from rest_framework import serializers
from django.utils import timezone

from .models import (
    TeamMember,
    SourceType,
    Source,
    SignalType,
    SignalCard,
    Signal,
    Category,
    Participant,
    SignalRaw
)


class SourceTypeSerializer(serializers.ModelSerializer):
    """Сериализатор для типов источников данных."""
    
    class Meta:
        model = SourceType
        fields = ['id', 'slug', 'name', 'description']
        read_only_fields = ['id']


class SourceSerializer(serializers.ModelSerializer):
    """Сериализатор для источников данных из социальных сетей."""
    source_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SourceType.objects.all(),
        source='source_type'
    )
    participant_id = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(),
        source='participant',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Source
        fields = [
            'id',
            'slug',
            'source_type_id',
            'participant_id',
            'tracking_enabled',
            'blocked',
            'nonexistent',
            'social_network_id'
        ]
        read_only_fields = ['id']


class SignalTypeSerializer(serializers.ModelSerializer):
    """Сериализатор для типов сигналов (инвестиция, партнёрство и т.д.)."""
    
    class Meta:
        model = SignalType
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категорий проектов."""
    parent_category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='parent_category',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent_category_id']
        read_only_fields = ['id']


class SignalCardSerializer(serializers.ModelSerializer):
    """Сериализатор для карточек проектов (SignalCard)."""
    
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        source='categories',
        write_only=True,
        required=False
    )

    class Meta:
        model = SignalCard
        fields = [
            'id',
            'slug',
            'name',
            'description',
            'url',
            'image',
            'stage',
            'round_status',
            'featured',
            'is_open',
            'reference_url',
            'last_round',
            'more',
            'categories',
            'category_ids',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SignalSerializer(serializers.ModelSerializer):
    """Сериализатор для сигналов (события от участников)."""
    
    source_id = serializers.PrimaryKeyRelatedField(
        queryset=Source.objects.all(),
        source='source'
    )
    signal_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalType.objects.all(),
        source='signal_type'
    )
    signal_card_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalCard.objects.all(),
        source='signal_card'
    )
    participant_id = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(),
        source='participant',
        required=False,
        allow_null=True
    )
    associated_participant_id = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(),
        source='associated_participant',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Signal
        fields = [
            'id',
            'source_id',
            'signal_type_id',
            'signal_card_id',
            'participant_id',
            'associated_participant_id',
            'linkedin_data',
            'more',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TeamMemberSerializer(serializers.ModelSerializer):
    """Сериализатор для членов команды проектов."""
    
    signal_card_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalCard.objects.all(),
        source='signal_card',
        required=False,
        allow_null=True
    )

    class Meta:
        model = TeamMember
        fields = [
            'id',
            'name',
            'headline',
            'image',
            'signal_card_id',
            'site',
            'crunchbase',
            'twitter',
            'linkedin',
            'instagram',
            'github',
            'producthunt'
        ]
        read_only_fields = ['id']


class ParticipantSerializer(serializers.ModelSerializer):
    """Сериализатор для участников (инвесторы, фонды, компании)."""
    
    associated_with_id = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(),
        source='associated_with',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Participant
        fields = [
            'id',
            'slug',
            'name',
            'additional_name',
            'image',
            'about',
            'type',
            'associated_with_id',
            'monthly_signals_count'
        ]
        read_only_fields = ['id', 'monthly_signals_count']


class SignalRawSerializer(serializers.ModelSerializer):
    """
    Сериализатор для сырых данных сигналов от микросервиса.
    
    Используется для приёма данных от микросервисов сбора данных
    и управления их обработкой.
    """
    
    # Связанные объекты
    source_id = serializers.PrimaryKeyRelatedField(
        queryset=Source.objects.all(),
        source='source',
        required=False,
        allow_null=True
    )
    
    signal_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalType.objects.all(),
        source='signal_type',
        required=False,
        allow_null=True
    )
    
    # Связанные объекты, заполняемые после обработки
    signal_card_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalCard.objects.all(),
        source='signal_card',
        required=False,
        allow_null=True
    )
    
    signal_id = serializers.PrimaryKeyRelatedField(
        queryset=Signal.objects.all(),
        source='signal',
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = SignalRaw
        fields = [
            'id',
            'is_processed',
            'source_id',
            'signal_type_id',
            'data',
            'label',
            'category',
            'stage',
            'round',
            'website',
            'description',
            'signal_card_id',
            'signal_id',
            'error_message',
            'created_at',
            'processed_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'processed_at',
            'created_at', 
            'updated_at'
        ]
    
    def validate_data(self, value):
        """Валидация JSON данных."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Поле 'data' должно быть JSON объектом")
        return value
    
    def update(self, instance, validated_data):
        """
        Обновление сырого сигнала.
        Автоматически устанавливает processed_at при is_processed=True.
        """
        # Если is_processed меняется на True, устанавливаем processed_at
        is_processed = validated_data.get('is_processed')
        if is_processed and not instance.is_processed:
            validated_data['processed_at'] = timezone.now()
        
        return super().update(instance, validated_data)
