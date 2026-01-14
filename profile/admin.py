from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm
from django.urls import path, reverse
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserCreationForm
from .models import (
    SavedCard, SavedParticipant, TicketForCard,
    DeletedCard, UserFeed,
    UserFolder, FolderCard, UserNote, SavedFilter,
    OnboardingStatus, UserGroup, GroupAssignedCard, GroupCardMemberAssignment,
)
from signals.models import Category, Participant

User = get_user_model()

@admin.register(DeletedCard)
class DeletedCardAdmin(ModelAdmin):
    list_display = ['user', 'signal_card']
    search_fields = ['user__username', 'signal_card__name']



@admin.register(SavedCard)
class SavedCardAdmin(ModelAdmin):
    list_display = ['user', 'signal_card']
    search_fields = ['user__username', 'signal_card__name']
    raw_id_fields = ['user', 'signal_card']

@admin.register(SavedParticipant)
class SavedParticipantAdmin(ModelAdmin):
    list_display = ['user', 'participant']
    search_fields = ['user__username', 'participant__name']
    raw_id_fields = ['user', 'participant']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "participant":
            kwargs["queryset"] = Participant.objects.filter(
                associated_with=F('id')
            ).order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(TicketForCard)
class TicketForCardAdmin(ModelAdmin):
    list_display = ['user', 'signal_card', 'created_at', 'is_processed']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['user__username', 'signal_card__name', 'response_text']
    raw_id_fields = ['user', 'signal_card']
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (None, {'fields': ['user', 'signal_card']}),
        ('Processing Information', {
            'fields': ['is_processed', 'response_text'],
            'classes': ['collapse']
        }),
    ]

    readonly_fields = ['created_at']

class UserAdmin(ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    change_user_password_template = None  # Добавлен этот атрибут
    
    list_display = [
        'username', 'email', 'first_name', 'last_name', 'group',
        'is_active', 'is_paid', 'last_login'
    ]
    list_filter = ['is_active', 'group']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']
    

    
    fieldsets = [
        (None, {'fields': ['username', 'password']}),
        ('Personal Information', {
            'fields': ['first_name', 'last_name', 'email', 'avatar'],
            'description': 'Основная информация о пользователе'
        }),
        ('Profile Settings', {
            'fields': ['user_type', 'group', 'is_paid'],
            'description': 'Настройки профиля и предпочтения'
        }),
        ('Permissions', {
            'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'],
            'description': 'Active: Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'
        }),
        ('Important Dates', {'fields': ['last_login', 'date_joined']}),
        ('User Statistics', {
            'fields': [
                'saved_cards_count', 'saved_participants_count', 'folders_count',
                'notes_count', 'saved_filters_count', 'worth_following_categories_count',
                'worth_following_participants_count'
            ],
            'classes': ['collapse'],
            'description': 'Статистика активности пользователя'
        }),
    ]
    
    readonly_fields = [
        'saved_cards_count', 'saved_participants_count', 'folders_count',
        'notes_count', 'saved_filters_count', 'worth_following_categories_count',
        'worth_following_participants_count'
    ]
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Переопределяем help_text для поля is_active"""
        if db_field.name == 'is_active':
            kwargs['help_text'] = 'Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': ['username', 'password1', 'password2'],
        }),
        ('Personal Information', {
            'fields': ['first_name', 'last_name', 'email', 'user_type'],
        }),
    ]

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                '<id>/password/',
                self.admin_site.admin_view(self.user_change_password),
                name='auth_user_password_change',
            ),
        ] + urls

    def user_change_password(self, request, id, form_url=''):
        user = self.get_object(request, id)
        if not self.has_change_permission(request, user):
            raise PermissionDenied
        return BaseUserAdmin.user_change_password(self, request, id, form_url)

    def get_form(self, request, obj=None, **kwargs):
        """
        Use special form during user creation
        """
        defaults = {}
        if obj is None:
            defaults['form'] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)
    

    
    def saved_cards_count(self, obj):
        """Количество сохраненных карточек"""
        return obj.saved_cards.count()
    saved_cards_count.short_description = 'Saved Cards'
    
    def saved_participants_count(self, obj):
        """Количество сохраненных участников"""
        return obj.saved_participants.count()
    saved_participants_count.short_description = 'Saved Participants'
    
    def folders_count(self, obj):
        """Количество папок"""
        return obj.user_folders.count()
    folders_count.short_description = 'Folders'
    
    def notes_count(self, obj):
        """Количество заметок"""
        return obj.user_notes.count()
    notes_count.short_description = 'Notes'
    
    def saved_filters_count(self, obj):
        """Количество сохраненных фильтров"""
        return obj.saved_filters.count()
    saved_filters_count.short_description = 'Saved Filters'
    
    def worth_following_categories_count(self, obj):
        """Количество категорий в Worth Following"""
        return 0
    worth_following_categories_count.short_description = 'Worth Following Categories'
    
    def worth_following_participants_count(self, obj):
        """Количество участников в Worth Following"""
        try:
            return 0
        except:
            return 0
    worth_following_participants_count.short_description = 'Worth Following Participants'

admin.site.register(User, UserAdmin)

class BaseFeedFilterAdmin(ModelAdmin):
    list_display = ['user', 'categories_display', 'stages_display', 
                   'participants_display']
    search_fields = ['user__username']
    list_filter = ['stages', 'round_statuses']
    filter_horizontal = ['categories', 'participants']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'categories', 'participants'
        )

    def categories_display(self, obj):
        return ', '.join(c.name for c in obj.categories.all()) or '-'
    categories_display.short_description = 'Categories'

    def stages_display(self, obj):
        return ', '.join(obj.stages) if obj.stages else '-'
    stages_display.short_description = 'Stages'

    def participants_display(self, obj):
        return ', '.join(p.name for p in obj.participants.all()) or '-'
    participants_display.short_description = 'Participants'

class UserFeedAdmin(BaseFeedFilterAdmin):
    fieldsets = [
        (None, {'fields': ['user']}),
        ('Filters', {
            'fields': [
                'stages', 'round_statuses', 'categories', 
                'participants'
            ],
            'description': 'Configure user feed filters'
        }),
    ]

admin.site.register(UserFeed, UserFeedAdmin)

@admin.register(UserFolder)
class UserFolderAdmin(ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'created_at', 'updated_at']
    list_filter = ['is_default', 'created_at', 'updated_at']
    search_fields = ['name', 'description', 'user__username']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (None, {'fields': ['user', 'name', 'description', 'is_default']}),
        ('Даты', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    readonly_fields = ['created_at', 'updated_at']

class FolderCardInline(TabularInline):
    model = FolderCard
    extra = 0
    raw_id_fields = ['signal_card']

@admin.register(FolderCard)
class FolderCardAdmin(ModelAdmin):
    list_display = ['folder', 'signal_card', 'added_at']
    list_filter = ['added_at']
    search_fields = ['folder__name', 'signal_card__name', 'folder__user__username']
    raw_id_fields = ['folder', 'signal_card']
    date_hierarchy = 'added_at'
    
    readonly_fields = ['added_at']

@admin.register(UserNote)
class UserNoteAdmin(ModelAdmin):
    list_display = ['user', 'signal_card', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'signal_card__name', 'note_text']
    raw_id_fields = ['user', 'signal_card']
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (None, {'fields': ['user', 'signal_card', 'note_text']}),
        ('Dates', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SavedFilter)
class SavedFilterAdmin(ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'created_at', 'updated_at', 'get_filter_summary_short']
    list_filter = ['is_default', 'created_at', 'stages', 'round_statuses']
    search_fields = ['name', 'description', 'user__username', 'search']
    filter_horizontal = ['categories', 'participants']
    readonly_fields = ['created_at', 'updated_at', 'get_filter_summary']
    
    fieldsets = [
        (None, {
            'fields': ['user', 'name', 'description', 'is_default']
        }),
        ('Search & Basic Filters', {
            'fields': ['search', 'featured', 'is_open'],
            'classes': ['collapse']
        }),
        ('Categories & Participants', {
            'fields': ['categories', 'participants'],
            'classes': ['collapse']
        }),
        ('Stages & Rounds', {
            'fields': ['stages', 'round_statuses'],
            'classes': ['collapse']
        }),
        ('Location & Date Filters', {
            'fields': ['locations', 'start_date', 'end_date'],
            'classes': ['collapse']
        }),
        ('Signal Count Filters', {
            'fields': ['min_signals', 'max_signals'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at', 'get_filter_summary'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'categories', 'participants'
        ).select_related('user')
    
    def get_filter_summary_short(self, obj):
        """Short version of filter summary for list display"""
        summary = obj.get_filter_summary()
        return summary[:100] + '...' if len(summary) > 100 else summary
    get_filter_summary_short.short_description = 'Filter Summary'
    
    def get_filter_summary(self, obj):
        """Full filter summary for detail view"""
        return obj.get_filter_summary()
    get_filter_summary.short_description = 'Complete Filter Summary'


@admin.register(OnboardingStatus)
class OnboardingStatusAdmin(ModelAdmin):
    list_display = ['user', 'status', 'last_step_key', 'completed_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['user__username', 'last_step_key']
    raw_id_fields = ['user']
    readonly_fields = ['updated_at']
    fieldsets = [
        (None, {'fields': ['user', 'status', 'last_step_key']}),
        ('Dates', {'fields': ['completed_at', 'updated_at'], 'classes': ['collapse']}),
    ]

@admin.register(GroupAssignedCard)
class GroupAssignedCardAdmin(ModelAdmin):
    list_display = ['group', 'signal_card', 'status', 'assigned_users_count', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'updated_at', 'group']
    search_fields = ['group__name', 'signal_card__name']
    raw_id_fields = ['group', 'signal_card']
    readonly_fields = ['created_at', 'updated_at', 'assigned_users_count']
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (None, {'fields': ['group', 'signal_card', 'status']}),
        ('Statistics', {
            'fields': ['assigned_users_count'],
            'classes': ['collapse']
        }),
        ('Dates', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def assigned_users_count(self, obj):
        """Returns the number of specifically assigned members to this card"""
        return obj.get_assigned_member_count()
    assigned_users_count.short_description = 'Assigned Members'

@admin.register(UserGroup)
class UserGroupAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'is_paid', 'member_count', 'created_at', 'updated_at']
    list_filter = ['is_paid', 'created_at', 'updated_at']
    search_fields = ['name', 'slug']
    
    def get_readonly_fields(self, request, obj=None):
        """Slug is readonly only for existing objects"""
        readonly = ['created_at', 'updated_at', 'member_count']
        if obj:  # Editing existing object
            readonly.append('slug')
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Different fieldsets for add and change"""
        if obj is None:  # Adding new object
            return [
                (None, {'fields': ['name', 'logo', 'is_paid']}),
            ]
        else:  # Editing existing object
            return [
                (None, {'fields': ['name', 'logo', 'is_paid']}),
                ('Additional Information', {
                    'fields': ['slug'],
                    'classes': ['collapse'],
                    'description': 'Slug is auto-generated from name'
                }),
                ('Statistics', {
                    'fields': ['member_count'],
                    'classes': ['collapse']
                }),
                ('Dates', {
                    'fields': ['created_at', 'updated_at'],
                    'classes': ['collapse']
                }),
            ]
    
    def member_count(self, obj):
        """Returns the number of group members with a link to filter users"""
        count = obj.get_member_count()
        if count > 0:
            url = reverse('admin:veck_profile_user_changelist') + f'?group__id__exact={obj.id}'
            return format_html('<a href="{}">{} участников</a>', url, count)
        return format_html('{} участников', count)
    member_count.short_description = 'Участники'


@admin.register(GroupCardMemberAssignment)
class GroupCardMemberAssignmentAdmin(ModelAdmin):
    list_display = ['group_assigned_card', 'user', 'assigned_by', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at', 'group_assigned_card__group']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'group_assigned_card__signal_card__name', 'assigned_by__username']
    raw_id_fields = ['group_assigned_card', 'user', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (None, {'fields': ['group_assigned_card', 'user', 'assigned_by']}),
        ('Dates', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]