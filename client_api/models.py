from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
import secrets
import hashlib

User = get_user_model()


class ClientAPIToken(models.Model):
    """
    Модель для постоянных токенов клиентского API.
    Каждый пользователь может иметь до 5 токенов.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='client_api_tokens',
        verbose_name="User"
    )
    name = models.CharField(
        max_length=100,
        help_text="Название токена для идентификации (например, 'Production API', 'Development')",
        verbose_name="Token Name"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Хеш токена (хранится только хеш, не сам токен)",
        verbose_name="Token Hash"
    )
    token_prefix = models.CharField(
        max_length=8,
        help_text="Префикс токена для отображения (первые 8 символов)",
        verbose_name="Token Prefix"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Активен ли токен",
        verbose_name="Is Active"
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Дата последнего использования токена",
        verbose_name="Last Used At"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    class Meta:
        verbose_name = "Client API Token"
        verbose_name_plural = "Client API Tokens"
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', 'is_active']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({self.token_prefix}...) - {status}"

    @staticmethod
    def generate_token():
        """
        Генерирует новый токен.
        Возвращает кортеж (полный_токен, хеш_токена, префикс)
        """
        # Генерируем случайный токен длиной 64 символа
        full_token = secrets.token_urlsafe(48)  # ~64 символа после кодирования
        # Создаем хеш токена для хранения в БД
        token_hash = hashlib.sha256(full_token.encode()).hexdigest()
        # Префикс для отображения (первые 8 символов)
        token_prefix = full_token[:8]
        return full_token, token_hash, token_prefix

    @staticmethod
    def hash_token(token):
        """Хеширует токен для проверки"""
        return hashlib.sha256(token.encode()).hexdigest()

    def is_valid(self):
        """Проверяет, валиден ли токен"""
        if not self.is_active:
            return False
        return True

    def mark_used(self):
        """Отмечает токен как использованный"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    def clean(self):
        """Валидация: максимум 5 токенов на пользователя"""
        if not self.pk and self.user_id:  # Только для новых токенов и если пользователь выбран
            active_tokens_count = ClientAPIToken.objects.filter(
                user_id=self.user_id,
                is_active=True
            ).count()
            if active_tokens_count >= 5:
                raise ValidationError(
                    f'User can have maximum 5 active tokens. Current count: {active_tokens_count}'
                )

    def save(self, *args, **kwargs):
        """Переопределяем save для вызова clean"""
        self.full_clean()
        super().save(*args, **kwargs)


class FreeUserRequestCounter(models.Model):
    """
    Модель для хранения счетчика запросов бесплатных пользователей/групп.
    Используется для персистентного хранения общего лимита (не дневного).
    """
    # Для пользователей без группы
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='free_request_counter',
        null=True,
        blank=True,
        unique=True,
        verbose_name="User",
        help_text="User (if no group)"
    )
    # Для групп
    group = models.ForeignKey(
        'profile.UserGroup',
        on_delete=models.CASCADE,
        related_name='free_request_counter',
        null=True,
        blank=True,
        unique=True,
        verbose_name="Group",
        help_text="Group (if user has group)"
    )
    request_count = models.IntegerField(
        default=0,
        verbose_name="Request Count",
        help_text="Total number of requests made"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    class Meta:
        verbose_name = "Free User Request Counter"
        verbose_name_plural = "Free User Request Counters"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['group']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(group__isnull=False),
                name='free_counter_user_or_group'
            ),
        ]

    def __str__(self):
        if self.user:
            return f"Free counter for user {self.user.username}: {self.request_count}"
        elif self.group:
            return f"Free counter for group {self.group.name}: {self.request_count}"
        return f"Free counter: {self.request_count}"

