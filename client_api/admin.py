from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import ClientAPIToken, FreeUserRequestCounter


class ClientAPITokenAdminForm(forms.ModelForm):
    """Форма с валидацией на максимум 5 токенов"""
    class Meta:
        model = ClientAPIToken
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        
        # Валидация только если пользователь выбран и это новый токен
        if user and not self.instance.pk:
            active_tokens_count = ClientAPIToken.objects.filter(
                user=user,
                is_active=True
            ).count()
            if active_tokens_count >= 5:
                raise ValidationError(
                    {
                        'user': f'User can have maximum 5 active tokens. Current count: {active_tokens_count}. '
                                f'Please deactivate or delete existing tokens first.'
                    }
                )
        return cleaned_data


@admin.register(ClientAPIToken)
class ClientAPITokenAdmin(ModelAdmin):
    form = ClientAPITokenAdminForm
    list_display = ['name', 'user', 'token_prefix', 'is_active', 'last_used_at', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'user__username', 'user__email', 'token_prefix']
    readonly_fields = ['token', 'token_prefix', 'created_at', 'last_used_at', 'token_display']
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name')
        }),
        ('Token Information', {
            'fields': ('token_display', 'token_prefix', 'token', 'is_active'),
            'description': 'Token prefix is shown for identification. Full token is only displayed once after creation.'
        }),
        ('Usage Information', {
            'fields': ('created_at', 'last_used_at')
        }),
    )

    def token_display(self, obj):
        """Отображает токен только при создании"""
        if obj.pk and hasattr(obj, '_full_token'):
            # Показываем полный токен только сразу после создания с предупреждением
            return mark_safe(
                f'<div style="background: #fff3cd; padding: 15px; border-radius: 5px; border: 2px solid #ffc107; margin: 10px 0;">'
                f'<strong style="color: #856404;">⚠️ IMPORTANT: Save this token now!</strong><br><br>'
                f'<code style="font-size: 14px; font-weight: bold; word-break: break-all; background: #fff; padding: 10px; border-radius: 3px; display: block; border: 1px solid #ffc107;">{obj._full_token}</code><br><br>'
                f'<strong style="color: #856404;">This token will NOT be shown again!</strong>'
                f'</div>'
            )
        elif obj.token_prefix:
            return mark_safe(
                f'<div style="background: #f0f0f0; padding: 10px; border-radius: 3px; display: inline-block;">'
                f'<code style="font-size: 12px;">{obj.token_prefix}...</code> '
                f'<span style="color: #666; font-size: 11px;">(full token hidden)</span>'
                f'</div>'
            )
        return 'Token will be generated after saving'
    token_display.short_description = 'Token'

    def has_change_permission(self, request, obj=None):
        """Разрешить изменение только своих токенов для не-суперпользователей"""
        if obj is not None and not request.user.is_superuser:
            return obj.user == request.user
        return True

    def has_delete_permission(self, request, obj=None):
        """Разрешить удаление только своих токенов для не-суперпользователей"""
        if obj is not None and not request.user.is_superuser:
            return obj.user == request.user
        return True

    def get_queryset(self, request):
        """Ограничить видимость токенов для не-суперпользователей"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('user')
        return qs.filter(user=request.user).select_related('user')

    def save_model(self, request, obj, form, change):
        """Переопределяем save для генерации токена при создании"""
        if not change:  # Если это новый объект
            full_token, token_hash, token_prefix = ClientAPIToken.generate_token()
            obj.token = token_hash
            obj.token_prefix = token_prefix
            # Сохраняем полный токен в объекте для отображения
            obj._full_token = full_token
        
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        """Показываем полный токен после создания"""
        response = super().response_add(request, obj, post_url_continue)
        
        if hasattr(obj, '_full_token'):
            full_token = obj._full_token
            from django.contrib import messages
            # Разбиваем на несколько сообщений для лучшей читаемости
            messages.warning(
                request,
                f'⚠️ IMPORTANT: Token "{obj.name}" created!'
            )
            messages.warning(
                request,
                f'Full token: {full_token}'
            )
            messages.warning(
                request,
                f'Save this token now - it will NOT be shown again!'
            )
        
        return response


@admin.register(FreeUserRequestCounter)
class FreeUserRequestCounterAdmin(ModelAdmin):
    """
    Админка для управления счетчиками бесплатных запросов.
    Показывает счетчики для пользователей и групп.
    """
    list_display = ['user_or_group', 'request_count', 'limit_info', 'remaining', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['user__username', 'user__email', 'group__name', 'group__slug']
    readonly_fields = ['request_count', 'updated_at', 'limit_info', 'remaining']
    raw_id_fields = ['user', 'group']
    
    fieldsets = (
        ('Entity Information', {
            'fields': ('user', 'group'),
            'description': 'Either user (if no group) or group (if user has group) must be set.'
        }),
        ('Request Counter', {
            'fields': ('request_count', 'limit_info', 'remaining'),
            'description': 'Current request count and limit information for free accounts.'
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ['collapse']
        }),
    )
    
    def user_or_group(self, obj):
        """Отображает пользователя или группу"""
        if obj.user:
            return f"User: {obj.user.username} ({obj.user.email})"
        elif obj.group:
            return f"Group: {obj.group.name} ({obj.group.slug})"
        return "-"
    user_or_group.short_description = 'User / Group'
    
    def limit_info(self, obj):
        """Показывает информацию о лимите"""
        from django.conf import settings
        limit = getattr(settings, 'FREE_CLIENT_LIMIT', 100)
        return f"{limit} requests total (free account)"
    limit_info.short_description = 'Limit'
    
    def remaining(self, obj):
        """Показывает оставшиеся запросы"""
        from django.conf import settings
        limit = getattr(settings, 'FREE_CLIENT_LIMIT', 100)
        remaining = max(0, limit - obj.request_count)
        percentage = (obj.request_count / limit * 100) if limit > 0 else 0
        
        if percentage >= 100:
            color = '#dc3545'  # red
            status = 'Exceeded'
        elif percentage >= 80:
            color = '#ffc107'  # yellow
            status = 'Warning'
        else:
            color = '#28a745'  # green
            status = 'OK'
        
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{remaining} remaining</span> '
            f'({obj.request_count}/{limit} used, {percentage:.1f}%)'
        )
    remaining.short_description = 'Remaining'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related('user', 'group')
    
    def has_add_permission(self, request):
        """Счетчики создаются автоматически, но можно разрешить ручное создание"""
        return True
    
    def has_change_permission(self, request, obj=None):
        """Разрешить изменение для суперпользователей"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Разрешить удаление для суперпользователей"""
        return request.user.is_superuser

