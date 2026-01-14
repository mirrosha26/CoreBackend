from unfold.admin import ModelAdmin
from django.contrib import admin
from django import forms
from django.utils import timezone
from django_json_widget.widgets import JSONEditorWidget
from .models import (
    TeamMember, SourceType, Source, SignalType, SignalCard, 
    Signal, Category, Participant,
    SignalCardStatusChange, SignalRaw, STAGES, ROUNDS
)


@admin.register(Participant)
class ParticipantAdmin(ModelAdmin):
    list_display = ['slug', 'name', 'type', 'monthly_signals_count', 'associated_with']
    search_fields = ['slug', 'name', 'type']
    list_filter = ['type', 'associated_with', 'monthly_signals_count']
    ordering = ['-monthly_signals_count', 'name']
    
    fieldsets = [
        ('Основная информация', {
            'fields': ['slug', 'name', 'type', 'associated_with']
        }),
        ('Активность', {
            'fields': ['monthly_signals_count'],
            'description': 'Количество сигналов за анализируемый период'
        }),
        ('Дополнительно', {
            'fields': ['about', 'image'],
            'description': 'Дополнительная информация об участнике'
        })
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('associated_with')


@admin.register(TeamMember)
class TeamMemberAdmin(ModelAdmin):
    list_display = ['name', 'signal_card']
    search_fields = ['name']
    list_filter = ['signal_card']


@admin.register(SourceType)
class SourceTypeAdmin(ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']


@admin.register(Source)
class SourceAdmin(ModelAdmin):
    list_display = ['slug', 'source_type', 'participant', 'tracking_enabled', 
                   'blocked', 'nonexistent', 'social_network_id']
    list_filter = ['source_type', 'participant', 'tracking_enabled', 
                  'blocked', 'nonexistent']
    search_fields = ['slug', 'source_type__name', 'participant__name']


@admin.register(SignalType)
class SignalTypeAdmin(ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']


@admin.register(SignalCard)
class SignalCardAdmin(ModelAdmin):
    list_display = ['name', 'uuid', 'url', 'created_at', 
                   'updated_at', 'is_open', 'featured', 'round_status']
    list_filter = ['created_at', 'updated_at', 'is_open', 
                  'featured', 'round_status']
    search_fields = ['name', 'description', 'uuid']
    readonly_fields = ['uuid']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'more':
            kwargs['widget'] = JSONEditorWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Signal)
class SignalAdmin(ModelAdmin):
    list_display = ['signal_type', 'signal_card', 'source', 'participant', 
                   'associated_participant', 'updated_at', 'created_at']
    list_filter = ['signal_type', 'source', 'participant', 'associated_participant']




class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent_category'].queryset = Category.objects.filter(
            parent_category__isnull=True
        )


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    form = CategoryAdminForm
    list_display = ['name', 'get_parent_category', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def get_parent_category(self, obj):
        return obj.parent_category.name if obj.parent_category else "No Parent"
    get_parent_category.short_description = 'Parent Category'


@admin.register(SignalCardStatusChange)
class SignalCardStatusChangeAdmin(ModelAdmin):
    list_display = ['signal_card', 'get_stage_change', 'get_round_change', 'created_at']
    list_filter = ['created_at', 'old_stage', 'new_stage', 'old_round_status', 'new_round_status']
    search_fields = ['signal_card__name', 'signal_card__slug']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = [
        ('Signal Card', {
            'fields': ['signal_card']
        }),
        ('Stage Changes', {
            'fields': ['old_stage', 'new_stage']
        }),
        ('Round Changes', {
            'fields': ['old_round_status', 'new_round_status']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_stage_change(self, obj):
        if obj.old_stage != obj.new_stage:
            old_display = dict(STAGES).get(obj.old_stage, obj.old_stage) if obj.old_stage else "None"
            new_display = dict(STAGES).get(obj.new_stage, obj.new_stage) if obj.new_stage else "None"
            return f"{old_display} → {new_display}"
        return "-"
    get_stage_change.short_description = 'Stage Change'
    
    def get_round_change(self, obj):
        if obj.old_round_status != obj.new_round_status:
            old_display = dict(ROUNDS).get(obj.old_round_status, obj.old_round_status) if obj.old_round_status else "None"
            new_display = dict(ROUNDS).get(obj.new_round_status, obj.new_round_status) if obj.new_round_status else "None"
            return f"{old_display} → {new_display}"
        return "-"
    get_round_change.short_description = 'Round Change'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('signal_card')


@admin.register(SignalRaw)
class SignalRawAdmin(ModelAdmin):
    """Админка для сырых данных сигналов от микросервиса."""
    
    list_display = [
        'id', 'is_processed', 'source', 'signal_type', 
        'label', 'category', 'stage', 'round', 
        'created_at', 'processed_at'
    ]
    
    list_filter = [
        'is_processed', 'source', 'signal_type', 
        'label', 'category', 'stage', 'round', 
        'created_at', 'processed_at'
    ]
    
    search_fields = [
        'id', 'source__slug', 
        'description', 'label', 'website', 'category'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    
    ordering = ['-created_at']
    
    fieldsets = [
        ('Статус обработки', {
            'fields': ['is_processed', 'processed_at']
        }),
        ('Источник данных', {
            'fields': ['source']
        }),
        ('Классификация', {
            'fields': ['signal_type', 'label', 'category']
        }),
        ('Данные проекта', {
            'fields': ['stage', 'round', 'website', 'description']
        }),
        ('Сырые данные', {
            'fields': ['data'],
            'classes': ['collapse'],
            'description': 'JSON данные от микросервиса'
        }),
        ('Связи (после обработки)', {
            'fields': ['signal_card', 'signal'],
            'classes': ['collapse']
        }),
        ('Ошибки', {
            'fields': ['error_message'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Использовать JSON редактор для JSON полей."""
        if db_field.name == 'data':
            kwargs['widget'] = JSONEditorWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        """Оптимизация запросов."""
        return super().get_queryset(request).select_related(
            'source', 'signal_type', 'signal_card', 'signal'
        )
    
    actions = ['mark_as_processed', 'mark_as_not_processed']
    
    def mark_as_processed(self, request, queryset):
        """Отметить как обработанные."""
        updated = queryset.update(is_processed=True, processed_at=timezone.now())
        self.message_user(request, f"{updated} сигналов отмечены как обработанные")
    mark_as_processed.short_description = "Отметить как обработанные"
    
    def mark_as_not_processed(self, request, queryset):
        """Отметить как необработанные."""
        updated = queryset.update(is_processed=False, error_message=None)
        self.message_user(request, f"{updated} сигналов возвращены в необработанные")
    mark_as_not_processed.short_description = "Вернуть в необработанные"
