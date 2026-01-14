from rest_framework import serializers
from profile.models import User, UserGroup
from .utils import build_absolute_image_url
from django.conf import settings


class UserGroupSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    
    def get_logo(self, obj):
        if obj.logo and hasattr(obj.logo, 'url'):
            return build_absolute_image_url(obj, True, field_name='logo', base_url=settings.BASE_IMAGE_URL)
        return None
    
    class Meta:
        model = UserGroup
        fields = ['id', 'name', 'slug', 'logo']
        read_only_fields = ['id', 'slug']


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    group = UserGroupSerializer(read_only=True, allow_null=True)
    
    def get_avatar(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return build_absolute_image_url(obj, True, field_name='avatar', base_url=settings.BASE_IMAGE_URL)
        return None
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type', 'avatar', 'group']
        read_only_fields = ['id', 'username'] 