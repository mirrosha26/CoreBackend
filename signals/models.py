"""
Модели для отслеживания сигналов инвесторов и стартапов.

Этот модуль содержит основные модели для системы отслеживания активности инвесторов,
включая участников (инвесторы, фонды), источники данных (социальные сети),
сигнальные карточки (стартапы) и сигналы (проявления интереса).
"""
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Count, F, Prefetch, Q, Value, When
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

# Removed unused imports from utils

# Стадии развития стартапов
STAGES = [
    ("unknown", "Unknown"),
    ("very_early", "Very Early"),
    ("worth_following", "Worth Following"),
    ("bootstrapped", "Bootstrapped"),
    ("founder_in_stealth", "Founder in Stealth"),
    ("came_out_of_stealth", "Came Out of Stealth"),
    ("pre_stealth", "Pre Stealth"),
    ("pre_seed", "Pre-seed"),
    ("seed", "Seed"),
    ("seed_plus", "Seed+"),
    ("angel_round", "Angel round"),
    ("strategic_round", "Strategic round"),
    ("series_a", "Series A"),
    ("series_b", "Series B"),
    ("series_c", "Series C"),
    ("series_d", "Series D"),
    ("series_e", "Series E"),
    ("series_f", "Series F"),
    ("founding_team", "Founding Team"),
    ("acquired", "Acquired"),
    ("hackathon", "Hackathon"),
    ("grant", "Grant"),
    ("pivoted", "Pivoted"),
]

# Статусы раундов финансирования
ROUNDS = [
    ("just_raised", "Just Raised"),
    ("about_to_raise", "About to Raise"),
    ("raising_now", "Raising Now"),
    ("may_be_raising", "May be raising"),
    ("unknown", "Unknown"),
    ("acquired", "Acquired"),
    ("gone_public", "Gone Public"),
    ("discontinued", "Discontinued"),
    ("possible_public_launch", "Possible Public Launch"),
]

# Типы участников экосистемы
PARTICIPANTS_TYPES = [
    ("fund", "Fund"),
    ("research", "Research"),
    ("investor", "Investor"),
    ("engineer", "Engineer"),
    ("angel", "Angel"),
    ("influencer", "Influencer"),
    ("unknown", "Unknown"),
    ("founder", "Founder"),
    ("scout", "Scout"),
    ("accelerator", "Accelerator"),
    ("platform", "Platform"),
    ("marketing", "Marketing"),
    ("writing", "Writing"),
    ("chief_of_staff", "Chief Of Staff"),
    ("talent_partner", "Talent Partner"),
    ("legal", "Legal"),
    ("operations", "Operations"),
    ("socials", "Socials"),
    ("business_development", "Business Development"),
    ("security", "Security"),
    ("finance", "Finance"),
    ("due_diligence", "Due Diligence"),
    ("data_science", "Data Science"),
    ("product", "Product"),
    ("protocol", "Protocol"),
    ("defi", "DeFi"),
    ("growth", "Growth"),
    ("design", "Design"),
    ("eir", "EIR"),
    ("data", "Data"),
    ("strategy", "Strategy"),
    ("raising_capital", "Raising Capital"),
    ("board", "Board"),
    ("analyst", "Analyst"),
    ("content", "Content"),
    ("investor_relations", "Investor Relations"),
    ("advisor", "Advisor"),
    ("ceo", "CEO"),
    ("portfolio", "Portfolio"),
    ("asset_management", "Asset Management"),
    ("events", "Events"),
    ("communications", "Communications"),
    ("community", "Community"),
    ("trading", "Trading"),
    ("syndicate", "Syndicate"),
    ("market_maker", "Market Maker"),
    ("GA", "GA"),
    ("company", "Company"),
    ("other", "Other"),
]


def get_image_path_by_slug(instance, filename):
    """Генерирует путь для загрузки изображения на основе slug экземпляра."""
    base_filename, file_extension = os.path.splitext(filename)
    new_filename = f"{slugify(instance.slug)}_{instance.pk}{file_extension}"
    return os.path.join(f"{instance._meta.model_name}", new_filename)


def get_image_path(instance, filename):
    """Генерирует путь для загрузки изображения на основе имени экземпляра."""
    base_filename, file_extension = os.path.splitext(filename)
    new_filename = f"{slugify(instance.name)}_{instance.pk}{file_extension}"
    return os.path.join(f"{instance._meta.model_name}", new_filename)


class Participant(models.Model):
    """
    Модель участника экосистемы стартапов.
    
    Представляет инвесторов, фонды, ангелов и других участников.
    Может быть связан с родительским участником (например, индивидуальный инвестор с фондом).
    """
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    additional_name = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to=get_image_path_by_slug, blank=True, null=True)
    associated_with = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="associations"
    )
    about = models.TextField(blank=True)
    type = models.CharField(max_length=255, choices=PARTICIPANTS_TYPES, default="unknown")
    monthly_signals_count = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        """Защита slug от изменения после создания для стабильности API."""
        if self.pk:
            old_slug = Participant.objects.get(pk=self.pk).slug
            if self.slug != old_slug:
                raise ValueError(
                    f"Cannot change slug for existing participant. "
                    f"Current slug: {old_slug}, attempted: {self.slug}"
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} {self.additional_name}".strip()

    def calculate_signals_count(self, days=30):
        """
        Подсчитывает количество сигналов участника за указанный период.
        Учитывает только сигналы, где участник является associated_participant.
        
        Args:
            days: Количество дней для анализа (по умолчанию: 30)
        
        Returns:
            Количество сигналов за период
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        return Signal.objects.filter(
            associated_participant=self,
            created_at__gte=start_date,
            signal_card__is_open=True
        ).count()

    def update_signals_count(self, days=30):
        """Обновляет поле monthly_signals_count для участника."""
        signals_count = self.calculate_signals_count(days)
        self.monthly_signals_count = signals_count
        self.save(update_fields=['monthly_signals_count'])
        return signals_count

    class Meta:
        indexes = [
            # Поиск по slug (уникальный, часто используется)
            models.Index(fields=['slug'], name='participant_slug_idx'),
            # Фильтрация по типу участника
            models.Index(fields=['type'], name='participant_type_idx'),
            # Композитный для поиска с фильтром по типу
            models.Index(fields=['name', 'type'], name='participant_name_type_idx'),
        ]

    objects = models.Manager()
    with_related = models.Manager()


class SourceType(models.Model):
    """Модель типа источника данных (Twitter, LinkedIn и т.д.)."""
    slug = models.SlugField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    profile_base_url = models.URLField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.slug


class Source(models.Model):
    """
    Модель источника данных из социальных сетей.
    
    Связывает участников с их профилями в социальных сетях для отслеживания сигналов.
    """
    slug = models.CharField(max_length=100)
    source_type = models.ForeignKey(
        'SourceType', on_delete=models.SET_NULL, null=True, related_name="sources"
    )
    participant = models.ForeignKey(
        'Participant', on_delete=models.CASCADE, blank=True, null=True, related_name="sources"
    )
    tracking_enabled = models.BooleanField(default=True)
    blocked = models.BooleanField(default=False)
    nonexistent = models.BooleanField(default=False)
    social_network_id = models.CharField(max_length=24, blank=True, null=True)

    def get_profile_link(self):
        if not self.source_type or not self.source_type.profile_base_url:
            return None
        return f"{self.source_type.profile_base_url}{self.slug}"

    def __str__(self):
        return f"{self.source_type} => {self.slug}"

    def clean(self):
        """Проверяет уникальность social_network_id в рамках типа источника."""
        if self.social_network_id and Source.objects.filter(
            social_network_id=self.social_network_id, 
            source_type=self.source_type
        ).exists():
            raise ValidationError(
                "This social_network_id already exists for this source type."
            )

    class Meta:
        unique_together = ("slug", "source_type")
        indexes = [
            # Поиск активных источников по типу и ID соцсети
            models.Index(fields=['source_type', 'social_network_id', 'tracking_enabled'], 
                        name='source_type_network_track_idx'),
            # Фильтрация источников участника
            models.Index(fields=['participant', 'tracking_enabled', 'blocked'], 
                        name='source_participant_status_idx'),
        ]

    objects = models.Manager()
    with_related = models.Manager()


class SignalType(models.Model):
    """Модель типа сигнала (например, подписка в Twitter, активность в LinkedIn)."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name or "Unnamed Type"


class Category(models.Model):
    """
    Модель иерархической категории для стартапов.
    
    Категории могут иметь родительско-дочерние связи для вложенной организации.
    """
    name = models.CharField(max_length=255)
    parent_category = models.ForeignKey(
        "self", on_delete=models.SET_NULL, blank=True, null=True, related_name="children"
    )
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        """Автоматически генерирует slug из имени, если не указан."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_all_children(self, include_self=True):
        """Рекурсивно получает все дочерние категории, опционально включая саму себя."""
        result = [self] if include_self else []
        for child in self.children.all():
            result.extend(child.get_all_children(include_self=True))
        return result

    class Meta:
        indexes = [
            # Поиск по slug с учетом иерархии
            models.Index(fields=['slug', 'parent_category'], name='category_slug_parent_idx'),
        ]


class SignalCardManager(models.Manager):
    """Кастомный менеджер для SignalCard с оптимизированной предзагрузкой."""
    
    def get_queryset(self):
        """Возвращает queryset с предзагруженными категориями."""
        return super().get_queryset().prefetch_related(
            'categories',
            'categories__parent_category'
        )

    def for_feed(self, user, categories=None, stages=None, round_statuses=None, min_sig=1, unique=False):
        """Получает сигнальные карточки для отображения в ленте."""
        return self.get_queryset().filter(is_open=True)


class SignalCardFeedManager(models.Manager):
    """Менеджер для оптимизированных запросов ленты с фильтрацией приватности."""
    
    def get_feed_queryset(self, user=None):
        """
        Получает оптимизированный queryset для отображения ленты с предзагрузкой связей.
        Применяет фильтрацию приватности, если передан пользователь.
        """
        base_qs = self.get_queryset().filter(is_open=True).prefetch_related(
            'categories',
            'categories__parent_category',
            Prefetch(
                'signals',
                queryset=Signal.objects.select_related(
                    'participant',
                    'associated_participant',
                    'source',
                    'source__source_type'
                )
            )
        )
        
        if user:
            # Применяем фильтр приватности на основе сохраненных участников
            private_filter = Q(
                signals__associated_participant__saved_by_users__user=user
            )
            base_qs = base_qs.filter(private_filter)
            
        return base_qs.distinct()

    def apply_feed_filters(self, queryset, user_feed=None, search_query=None, 
                          date_range=None, min_sig=1, max_sig=None, unique=False):
        """
        Применяет различные фильтры к queryset ленты.
        
        Args:
            queryset: Базовый queryset для фильтрации
            user_feed: Экземпляр UserFeed для персонализированной фильтрации
            search_query: Поисковый запрос для фильтрации по имени/описанию
            date_range: Фильтр по диапазону дат
            min_sig: Минимальное количество требуемых сигналов
            max_sig: Максимальное количество разрешенных сигналов
            unique: Считать ли только уникальных associated participants
        """
        # Обработка пустого списка участников - синхронизация или возврат пустого queryset
        if user_feed and not user_feed.participants.exists():
            from profile.models import SavedParticipant
            
            user = user_feed.user
            has_saved_participants = SavedParticipant.objects.filter(user=user).exists()
            
            if has_saved_participants:
                # Синхронизация сохраненных участников с UserFeed
                saved_participant_ids = SavedParticipant.objects.filter(
                    user=user
                ).values_list('participant_id', flat=True)
                participants = Participant.objects.filter(id__in=saved_participant_ids)
                user_feed.participants.set(participants)
                user_feed.save()
            else:
                return queryset.none()
            
        if min_sig > 1 or max_sig is not None:
            if unique:
                queryset = queryset.annotate(
                    signal_count=Count(
                        Case(
                            When(
                                signals__participant__associated_with__isnull=False,
                                then='signals__participant__associated_with'
                            ),
                            default='signals__participant',
                        ),
                        distinct=True
                    )
                )
                if min_sig > 1:
                    queryset = queryset.filter(signal_count__gte=min_sig)
                if max_sig is not None:
                    queryset = queryset.filter(signal_count__lte=max_sig)
            else:
                queryset = queryset.annotate(
                    signal_count=Count('signals__participant', distinct=True)
                )
                if min_sig > 1:
                    queryset = queryset.filter(signal_count__gte=min_sig)
                if max_sig is not None:
                    queryset = queryset.filter(signal_count__lte=max_sig)

        if user_feed:
            if user_feed.participants.exists():
                participant_ids = list(user_feed.participants.values_list('id', flat=True))
                queryset = queryset.filter(
                    Q(signals__participant_id__in=participant_ids) |
                    Q(signals__associated_participant_id__in=participant_ids)
                )

            if user_feed.categories.exists():
                category_ids = list(user_feed.categories.values_list('id', flat=True))
                queryset = queryset.filter(
                    Q(categories__id__in=category_ids) |
                    Q(categories__parent_category_id__in=category_ids)
                )

            if user_feed.stages or user_feed.round_statuses:
                stages_rounds_filter = Q()
                if user_feed.stages:
                    stages_rounds_filter |= Q(stage__in=user_feed.stages)
                if user_feed.round_statuses:
                    stages_rounds_filter |= Q(round_status__in=user_feed.round_statuses)
                queryset = queryset.filter(stages_rounds_filter)


        # Применяем поисковый запрос с оценкой релевантности
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(tags__name__icontains=search_query) |
                Q(categories__name__icontains=search_query) |
                Q(stage__icontains=search_query) |
                Q(round_status__icontains=search_query)
            )
            
            queryset = queryset.annotate(
                search_relevance=Case(
                    When(name__iexact=search_query, then=Value(100)),
                    When(name__icontains=search_query, then=Value(75)),
                    When(description__icontains=search_query, then=Value(25)),
                    default=Value(0),
                    output_field=models.IntegerField()
                )
            ).order_by('-search_relevance')
            
            return queryset.distinct()

        if date_range:
            queryset = queryset.filter(**date_range)

        return queryset.distinct()


class SignalCard(models.Model):
    """
    Модель сигнальной карточки стартапа/проекта.
    
    Содержит информацию о стадии финансирования, локации, команде и связанных сигналах.
    Основная модель для отслеживания стартапов в системе.
    """
    slug = models.SlugField(unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    image = models.ImageField(upload_to=get_image_path_by_slug, blank=True, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=1024)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
    last_round = models.DateField(null=True, blank=True)
    more = models.JSONField(blank=True, null=True)
    categories = models.ManyToManyField(Category, related_name="signal_cards", blank=True)
    stage = models.CharField(max_length=255, choices=STAGES, blank=True, null=True)
    is_open = models.BooleanField(default=True)
    reference_url = models.URLField(max_length=1024, blank=True, null=True)
    featured = models.BooleanField(default=False)
    round_status = models.CharField(max_length=255, choices=ROUNDS, default="unknown")

    def delete(self, *args, **kwargs):
        if self.image and hasattr(self.image, "path") and os.path.exists(self.image.path):
            self.image.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.name or "Unnamed Signal Card"

    class Meta:
        indexes = [
            # Основной индекс для ленты: открытые карточки по дате создания
            models.Index(fields=['is_open', 'created_at'], name='sc_feed_primary_idx'),
            # Фильтрация по стадии и раунду для открытых карточек
            models.Index(fields=['is_open', 'stage', 'round_status'], name='sc_filters_idx'),
            # Сортировка по дате обновления
            models.Index(fields=['is_open', 'updated_at'], name='sc_updated_idx'),
            # Избранные карточки
            models.Index(fields=['featured', 'is_open', 'created_at'], name='sc_featured_idx'),
            # Поиск по имени
            models.Index(fields=['name'], name='sc_name_idx'),
        ]

    objects = models.Manager()
    with_related = SignalCardManager()
    feed = SignalCardFeedManager()


class TeamMember(models.Model):
    """Модель члена команды стартапа."""
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to=get_image_path, blank=True, null=True)
    headline = models.TextField(blank=True, null=True)
    signal_card = models.ForeignKey(
        SignalCard, related_name="team_members", on_delete=models.CASCADE
    )
    site = models.URLField(max_length=1024, blank=True, null=True)
    crunchbase = models.URLField(max_length=1024, blank=True, null=True)
    twitter = models.URLField(max_length=1024, blank=True, null=True)
    linkedin = models.URLField(max_length=1024, blank=True, null=True)
    instagram = models.URLField(max_length=1024, blank=True, null=True)
    github = models.URLField(max_length=1024, blank=True, null=True)
    producthunt = models.URLField(max_length=1024, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def delete(self, *args, **kwargs):
        """Удаляет члена команды и связанный файл изображения."""
        if self.image and hasattr(self.image, "path") and os.path.exists(self.image.path):
            self.image.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.name or "Unnamed Member"


class SignalManager(models.Manager):
    """Кастомный менеджер для модели Signal с оптимизированной предзагрузкой связей."""
    
    def get_queryset(self):
        """Возвращает queryset с оптимизированными select_related и prefetch_related."""
        return super().get_queryset().select_related(
            'participant',
            'associated_participant',
            'source',
            'source__source_type',
            'signal_type'
        ).prefetch_related(
            'participant__sources',
            'participant__sources__source_type',
            'associated_participant__sources',
            'associated_participant__sources__source_type'
        )


class Signal(models.Model):
    """
    Модель сигнала интереса инвестора.
    
    Отслеживает, когда инвестор/участник проявляет интерес к стартапу (signal_card).
    """
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="signals")
    signal_type = models.ForeignKey(SignalType, on_delete=models.CASCADE, related_name="signals")
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name="signals")
    participant = models.ForeignKey(
        Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name="signals"
    )
    associated_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="associated_signals",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        """Возвращает строковое представление сигнала."""
        return f"{self.signal_type} signal from {self.participant} => {self.signal_card}"

    def save(self, *args, **kwargs):
        """
        Сохраняет сигнал и автоматически заполняет поля участников из источника.
        Устанавливает participant и associated_participant на основе участника источника.
        """
        if not self.pk:
            if self.source and hasattr(self.source, 'participant') and self.source.participant:
                self.participant = self.source.participant
                if (hasattr(self.source.participant, 'associated_with') and 
                    self.source.participant.associated_with):
                    self.associated_participant = self.source.participant.associated_with
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            # Основные запросы: сигналы карточки по дате с участником
            models.Index(fields=['signal_card', 'created_at'], name='signal_card_created_idx'),
            # Фильтрация по участникам с датой (покрывает несколько запросов)
            models.Index(fields=['participant', 'created_at'], name='signal_participant_date_idx'),
            models.Index(fields=['associated_participant', 'created_at'], name='signal_assoc_part_date_idx'),
            # Композитный для связи карточки и участников
            models.Index(fields=['signal_card', 'participant'], name='signal_card_part_idx'),
            models.Index(fields=['signal_card', 'associated_participant'], name='signal_card_assoc_idx'),
            # Фильтрация по типу сигнала
            models.Index(fields=['signal_type', 'created_at'], name='signal_type_date_idx'),
        ]

    objects = models.Manager()
    with_related = SignalManager()


class SourceManager(models.Manager):
    """Кастомный менеджер для модели Source с оптимизированной предзагрузкой source_type."""
    
    def get_queryset(self):
        """Возвращает queryset с предзагруженным source_type."""
        return super().get_queryset().select_related('source_type')


class SignalCardStatusChange(models.Model):
    """
    Модель для отслеживания изменений стадии и статуса раунда сигнальных карточек.
    
    Автоматически создается через post_save сигнал при изменении stage или round_status.
    """
    signal_card = models.ForeignKey(
        SignalCard, 
        on_delete=models.CASCADE, 
        related_name='status_changes'
    )
    old_stage = models.CharField(
        max_length=255, 
        choices=STAGES, 
        blank=True, 
        null=True,
        help_text="Предыдущая стадия"
    )
    new_stage = models.CharField(
        max_length=255, 
        choices=STAGES, 
        blank=True, 
        null=True,
        help_text="Новая стадия"
    )
    old_round_status = models.CharField(
        max_length=255, 
        choices=ROUNDS, 
        blank=True, 
        null=True,
        help_text="Предыдущий раунд"
    )
    new_round_status = models.CharField(
        max_length=255, 
        choices=ROUNDS, 
        blank=True, 
        null=True,
        help_text="Новый раунд"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # История изменений конкретной карточки
            models.Index(fields=['signal_card', 'created_at'], name='status_change_card_date_idx'),
            # Общая хронология изменений
            models.Index(fields=['created_at'], name='status_change_date_idx'),
        ]
    
    def __str__(self):
        """Возвращает читаемое представление изменения статуса."""
        changes = []
        
        if self.old_stage != self.new_stage:
            old_stage_display = (
                dict(STAGES).get(self.old_stage, self.old_stage) 
                if self.old_stage else "None"
            )
            new_stage_display = (
                dict(STAGES).get(self.new_stage, self.new_stage) 
                if self.new_stage else "None"
            )
            changes.append(f"Stage: {old_stage_display} → {new_stage_display}")
        
        if self.old_round_status != self.new_round_status:
            old_round_display = (
                dict(ROUNDS).get(self.old_round_status, self.old_round_status) 
                if self.old_round_status else "None"
            )
            new_round_display = (
                dict(ROUNDS).get(self.new_round_status, self.new_round_status) 
                if self.new_round_status else "None"
            )
            changes.append(f"Round: {old_round_display} → {new_round_display}")
        
        changes_str = ', '.join(changes) if changes else "No changes"
        date_str = self.created_at.strftime('%Y-%m-%d %H:%M')
        return f"{self.signal_card.name} - {changes_str} ({date_str})"


# Обработчики сигналов для отслеживания изменений SignalCard

@receiver(pre_save, sender=SignalCard)
def track_signal_card_changes(sender, instance, **kwargs):
    """
    Отслеживает изменения stage и round_status перед сохранением.
    Сохраняет оригинальные значения как атрибуты экземпляра для сравнения в post_save.
    """
    if instance.pk:
        try:
            original = SignalCard.objects.get(pk=instance.pk)
            instance._original_stage = original.stage
            instance._original_round_status = original.round_status
        except SignalCard.DoesNotExist:
            instance._original_stage = None
            instance._original_round_status = None
    else:
        instance._original_stage = None
        instance._original_round_status = None


@receiver(post_save, sender=SignalCard)
def create_status_change_record(sender, instance, created, **kwargs):
    """
    Создает запись SignalCardStatusChange после сохранения при изменении stage или round.
    Отслеживает изменения только для существующих записей, не для новых.
    """
    if created:
        return
    
    stage_changed = (
        hasattr(instance, '_original_stage') and 
        instance._original_stage != instance.stage
    )
    
    round_changed = (
        hasattr(instance, '_original_round_status') and 
        instance._original_round_status != instance.round_status
    )
    
    if stage_changed or round_changed:
        SignalCardStatusChange.objects.create(
            signal_card=instance,
            old_stage=instance._original_stage,
            new_stage=instance.stage,
            old_round_status=instance._original_round_status,
            new_round_status=instance.round_status
        )
    
        

class SignalRaw(models.Model):
    """
    Сырые данные сигналов от микросервиса сбора данных.
    
    Модель для хранения необработанных данных о сигналах до их проверки
    и преобразования в полноценные Signal и SignalCard записи.
    """
    
    # Источник данных
    source = models.ForeignKey(
        Source,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_drafts',
        verbose_name="Источник",
        help_text="Источник данных, который собрал эти данные"
    )
    
    # Тип сигнала
    signal_type = models.ForeignKey(
        SignalType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_drafts',
        verbose_name="Тип сигнала",
        help_text="Тип сигнала (инвестиция, партнёрство и т.д.)"
    )
    
    # Сырые данные в JSON
    data = models.JSONField(
        verbose_name="Сырые данные",
        help_text="Полные необработанные данные от микросервиса в JSON формате"
    )
    
    # Статус обработки
    is_processed = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Обработан",
        help_text="Флаг обработки черновика"
    )
    
    # Базовая классификация (project/noise/uncertain)
    label = models.TextField(
        null=True,
        blank=True,
        verbose_name="Базовая метка",
        help_text="Базовая классификация: project, noise, uncertain и т.д."
    )
    
    # Метки классификации
    category = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Категория",
        help_text="Категория проекта (ai, fintech, etc.)"
    )
    
    stage = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Стадия",
        help_text="Стадия развития проекта (seed, ideation, etc.)"
    )
    
    round = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Раунд",
        help_text="Раунд финансирования (seed, series-a, etc.)"
    )
    
    # Данные проекта
    website = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Вебсайт",
        help_text="Веб-сайт проекта"
    )
    
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Описание",
        help_text="Описание проекта или сигнала"
    )
    
    # Связи с обработанными данными (заполняются после обработки)
    signal_card = models.ForeignKey(
        SignalCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_drafts',
        verbose_name="Связанная карточка",
        help_text="SignalCard, созданная из этого черновика"
    )
    
    signal = models.ForeignKey(
        Signal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_draft',
        verbose_name="Связанный сигнал",
        help_text="Signal, созданный из этого черновика"
    )
    
    # Обработка ошибок
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Сообщение об ошибке",
        help_text="Описание ошибки при обработке"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        help_text="Дата и время получения данных от микросервиса"
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата обработки",
        help_text="Дата и время обработки черновика"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        db_table = 'signals_signal_raw'
        verbose_name = "Сырой сигнал"
        verbose_name_plural = "Сырые сигналы"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_processed', '-created_at'], name='sigraw_processed_created_idx'),
            models.Index(fields=['source', 'is_processed'], name='sigraw_source_processed_idx'),
            models.Index(fields=['-created_at'], name='sigraw_created_idx'),
            models.Index(fields=['stage', 'round'], name='sigraw_stage_round_idx'),
            models.Index(fields=['category'], name='sigraw_category_idx'),
            models.Index(fields=['processed_at'], name='sigraw_processed_at_idx'),
        ]
    
    def __str__(self):
        """Строковое представление сырого сигнала."""
        source_name = self.source.slug if self.source else "Unknown"
        status = "✓" if self.is_processed else "○"
        return f"SignalRaw #{self.id} {status} from {source_name}"