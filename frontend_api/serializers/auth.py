from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Простой сериализатор для запроса сброса пароля
    """
    email = serializers.EmailField(
        max_length=254,
        help_text="Email пользователя для сброса пароля"
    )


class PasswordResetResponseSerializer(serializers.Serializer):
    """
    Сериализатор для ответа на запрос сброса пароля
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    error = serializers.CharField(required=False, allow_blank=True) 