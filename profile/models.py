from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.constraints import UniqueConstraint
from signals.models import SignalCard, Participant, STAGES, ROUNDS, Category, Source
from django.core.exceptions import ValidationError
from multiselectfield import MultiSelectField
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.db import transaction
from .cache_utils import safe_delete_pattern, safe_cache_get, safe_cache_set
from django.utils import timezone
from django.utils.text import slugify

def get_image_path_by_slug(instance, filename):
    return f'images/{instance.pk}/{filename}'

def get_avatar_path(instance, filename):
    return f'user_avatars/{instance.pk}/{filename}'

# Добавить константу для типов пользователей
USER_TYPES = [
    ('VC', 'Venture Capital'),
    ('PE', 'Private Equity'),
    ('ANGEL', 'Angel'),
    ('FOUNDER', 'Founder'),
    ('SYNDICATE', 'Syndicate'),
    ('ACCELERATOR', 'Accelerator'),
    ('PRIVATE', 'Private investor'),
    ('OTHER', 'Other'),
]

class User(AbstractUser):
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='VC')
    avatar = models.ImageField(upload_to=get_avatar_path, blank=True, null=True, verbose_name="Аватар пользователя")
    group = models.ForeignKey(
        'UserGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name="Group"
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Paid Access (API)",
        help_text="If True, user has paid API access (daily limit). If False, free access (total limit). Only used if user has no group."
    )
    
    def __str__(self):
        return self.username


class UserGroup(models.Model):
    """
    User group model (fund, organization).
    Allows to unite multiple employees under one group
    for shared functionality and sharing.
    """
    name = models.CharField(max_length=255, verbose_name="Group Name")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="URL Slug")
    logo = models.ImageField(
        upload_to='group_logos/',
        blank=True,
        null=True,
        verbose_name="Group Logo"
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Paid Access (API)",
        help_text="If True, group has paid API access (daily limit). If False, free access (total limit)."
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = "User Group"
        verbose_name_plural = "User Groups"
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure slug is unique
            original_slug = self.slug
            counter = 1
            while UserGroup.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_member_count(self):
        """Returns the number of group members"""
        return self.members.count()


class OnboardingStatus(models.Model):
    """Персональный статус онбординга пользователя."""
    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("SKIPPED", "Skipped"),
        ("DISABLED", "Disabled"),  # Полностью отключен
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="onboarding_status")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DISABLED")
    last_step_key = models.CharField(max_length=100, blank=True, null=True, help_text="Ключ последнего шага")
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Onboarding({self.user.username}): {self.status} / {self.last_step_key or '-'}"


@receiver(post_save, sender=User)
def create_onboarding_status(sender, instance, created, **kwargs):
    if created:
        OnboardingStatus.objects.create(user=instance)

class SavedCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_cards')
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name='saved_by_users')

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'signal_card'], name='unique_saved_card_per_user')
        ]
        indexes = [
            models.Index(fields=['user', 'signal_card']),
            models.Index(fields=['signal_card'])
        ]

    def __str__(self):
        return f"{self.user.username} saved {self.signal_card.name}"


class DeletedCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deleted_cards')
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name='deleted_by_users')

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'signal_card'], name='unique_deleted_card_per_user')
        ]
        indexes = [
            models.Index(fields=['user', 'signal_card']),
            models.Index(fields=['signal_card'])
        ]

    def __str__(self):
        return f"{self.user.username} deleted {self.signal_card.name}"


class GroupAssignedCard(models.Model):
    """
    Represents a card assignment to a group in the pipeline.
    
    This model stores the overall assignment of a card to a group with status tracking.
    It represents the card in the group's pipeline/workflow.
    
    Key features:
    - Group-level card assignment with status (REVIEW=Review, REACHING_OUT=Reaching out, CONNECTED=Connected, NOT_A_FIT=Not a Fit)
    - Tracks when the card was assigned to the group
    - Individual member assignments are tracked separately in GroupCardMemberAssignment
    """
    STATUS_CHOICES = [
        ('REVIEW', 'Review (initial screening before outreach)'),  # Initial screening before outreach
        ('REACHING_OUT', 'Reaching out (outreach in progress)'),  # Outreach in progress
        ('CONNECTED', 'Connected'),  # Connected
        ('NOT_A_FIT', 'Not a Fit (No further action. Not relevant or no response after outreach.)'),  # Not a Fit
    ]
    
    group = models.ForeignKey(
        UserGroup,
        on_delete=models.CASCADE,
        related_name='assigned_cards',
        verbose_name="Group",
        help_text="The group this card is assigned to"
    )
    signal_card = models.ForeignKey(
        SignalCard,
        on_delete=models.CASCADE,
        related_name='assigned_to_groups',
        verbose_name="Signal Card",
        help_text="The card assigned to the group"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='REVIEW',
        verbose_name="Status",
        help_text="Overall status of the card assignment for the group"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Group Assigned Card"
        verbose_name_plural = "Group Assigned Cards"
        constraints = [
            UniqueConstraint(
                fields=['group', 'signal_card'],
                name='unique_group_assigned_card'
            )
        ]
        indexes = [
            models.Index(fields=['group', 'signal_card']),
            models.Index(fields=['signal_card']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.group.name} → {self.signal_card.name} ({self.get_status_display()})"
    
    def get_assigned_members(self):
        """Returns members specifically assigned to this card"""
        return User.objects.filter(group_card_assignments__group_assigned_card=self).distinct()
    
    def get_assigned_member_count(self):
        """Returns the count of specifically assigned members"""
        return self.member_assignments.count()
    
    def get_all_group_members(self):
        """Returns all members of the group"""
        return self.group.members.all()
    
    def get_all_group_member_count(self):
        """Returns the total count of group members"""
        return self.group.members.count()
    
    def is_member_assigned(self, user):
        """Check if a specific member is assigned to this card"""
        return self.member_assignments.filter(user=user).exists()


class GroupCardMemberAssignment(models.Model):
    """
    Model for individual member assignments to a card.
    
    This model tracks specific assignments of group members to cards,
    storing information about who assigned whom and when.
    
    Separate from GroupAssignedCard which tracks the overall card status in the pipeline.
    """
    group_assigned_card = models.ForeignKey(
        GroupAssignedCard,
        on_delete=models.CASCADE,
        related_name='member_assignments',
        verbose_name="Group Assigned Card",
        help_text="The group card assignment this member assignment belongs to"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_card_assignments',
        verbose_name="User",
        help_text="The group member assigned to work on the card"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_group_members',
        verbose_name="Assigned By",
        help_text="The user who made this assignment"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Group Card Member Assignment"
        verbose_name_plural = "Group Card Member Assignments"
        constraints = [
            UniqueConstraint(
                fields=['group_assigned_card', 'user'],
                name='unique_group_card_member_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['group_assigned_card', 'user']),
            models.Index(fields=['user']),
            models.Index(fields=['group_assigned_card']),
            models.Index(fields=['assigned_by']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        assigner = self.assigned_by.username if self.assigned_by else "System"
        return f"{self.user.username} → {self.group_assigned_card.signal_card.name} (by {assigner})"
    
    def clean(self):
        """Validate that the assigned user is a member of the group"""
        from django.core.exceptions import ValidationError
        
        if self.group_assigned_card and self.user:
            if not self.group_assigned_card.group.members.filter(id=self.user.id).exists():
                raise ValidationError(
                    f"User {self.user.username} is not a member of group {self.group_assigned_card.group.name}"
                )
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


class SavedParticipant(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='saved_participants')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='saved_by_users')
    in_digest = models.BooleanField(
        default=False,
        help_text="Include this participant in digest notifications"
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'participant'], name='unique_saved_participant_per_user')
        ]
        indexes = [
            models.Index(fields=['user', 'participant']),
            models.Index(fields=['participant']),
            models.Index(fields=['in_digest'])
        ]

    def __str__(self):
        return f"{self.user.username} saved {self.participant.name}"

class TicketForCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_contacts')
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name='contact_requests')
    created_at = models.DateTimeField(auto_now_add=True) 
    is_processed = models.BooleanField(default=False)
    response_text = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'signal_card'], name='unique_contact_request_per_user')
        ]

    def __str__(self):
        status = "processed" if self.is_processed else "pending"
        return f"{self.user.username} requested contact for {self.signal_card.name} (Status: {status})"


class UserFeed(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_feed')
    stages = MultiSelectField(choices=STAGES, max_choices=20, max_length=500, null=True, blank=True)
    round_statuses = MultiSelectField(choices=ROUNDS, max_choices=20, max_length=500, null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True)
    participants = models.ManyToManyField(Participant, blank=True)

    def __str__(self):
        return f"Feed Settings for {self.user.username}"

# Сигналы для автоматического создания UserFeed при создании пользователя
@receiver(post_save, sender=User)
def create_user_feed(sender, instance, created, **kwargs):
    if created:
        UserFeed.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_feed(sender, instance, **kwargs):
    instance.user_feed.save()


class UserFolder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_folders')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)  # Флаг для папки "Избранное"
    in_digest = models.BooleanField(
        default=False,
        help_text="Include this folder in digest notifications"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'name'], name='unique_folder_name_per_user')
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_default']),
            models.Index(fields=['in_digest']),
            models.Index(fields=['created_at'])
        ]
    
    def __str__(self):
        return f"{self.name} (Папка пользователя {self.user.username})"
    
    def save(self, *args, **kwargs):
        # Проверяем, что у пользователя может быть только одна папка по умолчанию
        if self.is_default:
            UserFolder.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
        
    def delete(self, *args, **kwargs):
        if self.is_default:
            raise ValueError("Нельзя удалить папку по умолчанию")
        super().delete(*args, **kwargs)


class FolderCard(models.Model):
    folder = models.ForeignKey(UserFolder, on_delete=models.CASCADE, related_name='folder_cards')
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name='in_folders')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            UniqueConstraint(fields=['folder', 'signal_card'], name='unique_card_per_folder')
        ]
        indexes = [
            models.Index(fields=['folder']),
            models.Index(fields=['signal_card'])
        ]
    
    def __str__(self):
        return f"Карточка {self.signal_card.name} в папке {self.folder.name}"


@receiver(post_save, sender=User)
def create_default_folder(sender, instance, created, **kwargs):
    """Создает папку 'Favorites' для нового пользователя"""
    if created:
        UserFolder.objects.create(
            user=instance,
            name="Favorites",
            description="Папка для избранных карточек",
            is_default=True
        )


# Миграция данных из SavedCard в FolderCard
def migrate_saved_cards():
    """
    Функция для миграции данных из SavedCard в FolderCard.
    Запустить после применения миграций.
    """
    for saved_card in SavedCard.objects.all():
        default_folder, created = UserFolder.objects.get_or_create(
            user=saved_card.user,
            is_default=True,
            defaults={'name': 'Favorites', 'description': 'Папка для избранных карточек'}
        )
        FolderCard.objects.get_or_create(
            folder=default_folder,
            signal_card=saved_card.signal_card
        )


class UserNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notes')
    signal_card = models.ForeignKey(SignalCard, on_delete=models.CASCADE, related_name='card_notes')
    note_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'signal_card'], name='unique_note_per_user_card')
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['signal_card']),
        ]
    
    def __str__(self):
        return f"Note by {self.user.username} on {self.signal_card.name}"


class SavedFilter(models.Model):
    """
    Model for saving named filter configurations that users can reuse.
    Each user can have multiple saved filters with custom names.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_filters')
    name = models.CharField(max_length=100, help_text="User-defined name for this filter")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the filter")
    in_digest = models.BooleanField(
        default=False,
        help_text="Include this filter in digest notifications"
    )
    
    # Filter configuration fields (matching SignalCardFilters)
    stages = MultiSelectField(choices=STAGES, max_choices=20, max_length=500, null=True, blank=True)
    round_statuses = MultiSelectField(choices=ROUNDS, max_choices=20, max_length=500, null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True)
    participants = models.ManyToManyField(Participant, blank=True)
    
    # Advanced participant filtering fields
    PARTICIPANT_FILTER_MODE_CHOICES = [
        ('INCLUDE_ONLY', 'Include Only'),
        ('EXCLUDE_FROM_TYPE', 'Exclude From Type'),
    ]
    participant_filter_mode = models.CharField(
        max_length=20, 
        choices=PARTICIPANT_FILTER_MODE_CHOICES, 
        null=True, 
        blank=True,
        help_text="Mode for advanced participant filtering"
    )
    participant_filter_ids = models.JSONField(
        null=True, 
        blank=True,
        help_text="List of participant IDs to include/exclude based on mode"
    )
    participant_filter_types = models.JSONField(
        null=True, 
        blank=True,
        help_text="List of participant types for filtering (e.g., ['angel', 'investor'])"
    )
    
    # Additional filter fields
    search = models.CharField(max_length=255, blank=True, null=True, help_text="Search query")
    featured = models.BooleanField(null=True, blank=True, help_text="Filter for featured cards")
    is_open = models.BooleanField(null=True, blank=True, help_text="Filter for open/closed cards")
    new = models.BooleanField(null=True, blank=True, help_text="Filter for cards created in the last 7 days")
    trending = models.BooleanField(null=True, blank=True, help_text="Filter for trending projects (at least 5 signals in last week)")
    hide_liked = models.BooleanField(null=True, blank=True, help_text="Filter out cards liked by the user")
    start_date = models.DateField(null=True, blank=True, help_text="Filter start date")
    end_date = models.DateField(null=True, blank=True, help_text="Filter end date")
    min_signals = models.PositiveIntegerField(null=True, blank=True, help_text="Minimum signals count")
    max_signals = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum signals count")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_default = models.BooleanField(default=False, help_text="Whether this is the user's default filter")
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_saved_filter_name_per_user'),
            models.UniqueConstraint(
                fields=['user'], 
                condition=models.Q(is_default=True),
                name='unique_default_filter_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
        ordering = ['-updated_at', 'name']
    
    def __str__(self):
        return f"Saved Filter '{self.name}' for {self.user.username}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default filter per user
        if self.is_default:
            SavedFilter.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        
        # Clear related caches when saving
        if self.pk:  # Only for updates, not new objects
            safe_delete_pattern(f"filter_summary:{self.pk}:*")
            safe_delete_pattern(f"saved_filters:{self.user.id}:*")
        
        super().save(*args, **kwargs)
        
        # Clear caches after save too (for new objects)
        safe_delete_pattern(f"saved_filters:{self.user.id}:*")
    
    def get_filter_summary(self):
        """
        Returns a human-readable summary of the filter configuration.
        Optimized with caching and reduced database queries.
        """
        # Check cache first
        cache_key = f"filter_summary:{self.id}:{self.updated_at.timestamp()}"
        cached_summary = safe_cache_get(cache_key)
        if cached_summary is not None:
            return cached_summary
        
        summary_parts = []
        
        if self.search:
            summary_parts.append(f"Search: '{self.search}'")
        
        # Optimize: Single query for categories with exists() check
        if hasattr(self, '_prefetched_objects_cache') and 'categories' in self._prefetched_objects_cache:
            # Use prefetched data if available
            categories = [cat.name for cat in self.categories.all()]
        else:
            # Fall back to efficient single query
            categories = list(self.categories.values_list('name', flat=True))
        
        if categories:
            summary_parts.append(f"Categories: {', '.join(categories[:3])}{' (+more)' if len(categories) > 3 else ''}")
        
        # Handle both legacy and advanced participant filtering
        participant_summary_parts = []
        
        # Legacy participant filtering
        if hasattr(self, '_prefetched_objects_cache') and 'participants' in self._prefetched_objects_cache:
            # Use prefetched data if available
            participants = [part.name for part in self.participants.all()]
        else:
            # Fall back to efficient single query
            participants = list(self.participants.values_list('name', flat=True))
        
        if participants:
            participant_summary_parts.append(f"Selected: {', '.join(participants[:3])}{' (+more)' if len(participants) > 3 else ''}")
        
        # Advanced participant filtering
        if self.participant_filter_mode:
            if self.participant_filter_mode == 'INCLUDE_ONLY':
                if self.participant_filter_ids:
                    # Get participant names for the IDs
                    from signals.models import Participant
                    filter_participants = list(Participant.objects.filter(
                        id__in=self.participant_filter_ids
                    ).values_list('name', flat=True))
                    if filter_participants:
                        participant_summary_parts.append(f"Include only: {', '.join(filter_participants[:3])}{' (+more)' if len(filter_participants) > 3 else ''}")
            elif self.participant_filter_mode == 'EXCLUDE_FROM_TYPE':
                type_parts = []
                if self.participant_filter_types:
                    type_parts.append(f"Types: {', '.join(self.participant_filter_types)}")
                if self.participant_filter_ids:
                    # Get participant names for the excluded IDs
                    from signals.models import Participant
                    excluded_participants = list(Participant.objects.filter(
                        id__in=self.participant_filter_ids
                    ).values_list('name', flat=True))
                    if excluded_participants:
                        type_parts.append(f"Exclude: {', '.join(excluded_participants[:3])}{' (+more)' if len(excluded_participants) > 3 else ''}")
                if type_parts:
                    participant_summary_parts.append(f"Filter by type ({', '.join(type_parts)})")
        
        if participant_summary_parts:
            summary_parts.append(f"Participants: {' | '.join(participant_summary_parts)}")
        
        if self.stages:
            stage_names = [dict(STAGES).get(stage, stage) for stage in self.stages]
            summary_parts.append(f"Stages: {', '.join(stage_names[:3])}{' (+more)' if len(stage_names) > 3 else ''}")
        
        if self.round_statuses:
            round_names = [dict(ROUNDS).get(round_status, round_status) for round_status in self.round_statuses]
            summary_parts.append(f"Rounds: {', '.join(round_names[:3])}{' (+more)' if len(round_names) > 3 else ''}")
        
        if self.featured is not None:
            summary_parts.append(f"Featured: {'Yes' if self.featured else 'No'}")
        
        if self.is_open is not None:
            summary_parts.append(f"Open: {'Yes' if self.is_open else 'No'}")
        
        if self.new is not None:
            summary_parts.append(f"New: {'Yes' if self.new else 'No'}")
        
        if self.trending is not None:
            summary_parts.append(f"Trending: {'Yes' if self.trending else 'No'}")
        
        if self.hide_liked is not None:
            summary_parts.append(f"Hide Liked: {'Yes' if self.hide_liked else 'No'}")
        
        if self.start_date or self.end_date:
            date_range = []
            if self.start_date:
                date_range.append(f"from {self.start_date.strftime('%d.%m.%Y')}")
            if self.end_date:
                date_range.append(f"to {self.end_date.strftime('%d.%m.%Y')}")
            summary_parts.append(f"Date: {' '.join(date_range)}")
        
        if self.min_signals is not None or self.max_signals is not None:
            signal_range = []
            if self.min_signals is not None:
                signal_range.append(f"min {self.min_signals}")
            if self.max_signals is not None:
                signal_range.append(f"max {self.max_signals}")
            summary_parts.append(f"Signals: {', '.join(signal_range)}")
        
        summary = "; ".join(summary_parts) if summary_parts else "No filters applied"
        
        # Cache the result for 15 minutes
        safe_cache_set(cache_key, summary, 900)
        
        return summary


@receiver(pre_save, sender=User)
def handle_user_group_change(sender, instance, **kwargs):
    """
    Handle user joining or leaving a group, and paid status changes.
    When user's group changes:
    - If joining a group: transfer free user request counter from user to group
    - If leaving a group: user assignments are removed (but GroupAssignedCard records remain)
    When user's is_paid changes from False to True:
    - Delete free request counter (no longer needed for paid users)
    """
    if instance.pk:  # Only for existing users
        try:
            old_user = User.objects.get(pk=instance.pk)
            old_group = old_user.group
            new_group = instance.group
            old_is_paid = old_user.is_paid
            new_is_paid = instance.is_paid
            
            # If user joined a group (group changed from None to something, or to different group)
            if not old_group and new_group:
                # User joined a group - transfer free request counter from user to group
                try:
                    from client_api.models import FreeUserRequestCounter
                    
                    # Получаем счетчик пользователя (если есть)
                    user_counter = FreeUserRequestCounter.objects.filter(user=instance).first()
                    
                    if user_counter and user_counter.request_count > 0:
                        # Получаем или создаем счетчик группы
                        group_counter, created = FreeUserRequestCounter.objects.get_or_create(
                            group=new_group,
                            defaults={'request_count': 0}
                        )
                        
                        # Переносим запросы: добавляем к счетчику группы
                        group_counter.request_count += user_counter.request_count
                        group_counter.save(update_fields=['request_count', 'updated_at'])
                        
                        # Удаляем счетчик пользователя
                        user_counter.delete()
                except ImportError:
                    # Если модель недоступна, пропускаем
                    pass
                except Exception as e:
                    # Логируем ошибку, но не прерываем сохранение пользователя
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error transferring free request counter: {e}")
            
            # If user's is_paid changed from False to True (and user has no group)
            if not new_group and old_is_paid == False and new_is_paid == True:
                # User upgraded to paid - delete free request counter (no longer needed)
                try:
                    from client_api.models import FreeUserRequestCounter
                    FreeUserRequestCounter.objects.filter(user=instance).delete()
                except ImportError:
                    pass
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting free request counter: {e}")
            
            # If user left the group (group changed from something to None or different)
            if old_group and old_group != new_group:
                # User left the group - they are no longer assigned to cards
                # The GroupAssignedCard records remain, but user is not in group anymore
                # So they won't be returned by get_assigned_users()
                # Clear cache if needed
                from graphql_app.mutations import invalidate_user_cache_after_mutation
                invalidate_user_cache_after_mutation(instance.id)
        except User.DoesNotExist:
            pass  # New user, nothing to do


@receiver(pre_save, sender=UserGroup)
def handle_group_paid_status_change(sender, instance, **kwargs):
    """
    Handle group paid status change.
    When group's is_paid changes from False to True:
    - Delete free request counter (no longer needed for paid groups)
    """
    if instance.pk:  # Only for existing groups
        try:
            old_group = UserGroup.objects.get(pk=instance.pk)
            old_is_paid = old_group.is_paid
            new_is_paid = instance.is_paid
            
            # If group's is_paid changed from False to True
            if old_is_paid == False and new_is_paid == True:
                # Group upgraded to paid - delete free request counter (no longer needed)
                try:
                    from client_api.models import FreeUserRequestCounter
                    FreeUserRequestCounter.objects.filter(group=instance).delete()
                except ImportError:
                    pass
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting free request counter for group: {e}")
        except UserGroup.DoesNotExist:
            pass  # New group, nothing to do