from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from frontend_api.serializers import UserSerializer, UserGroupSerializer
from django.utils import timezone
from profile.models import UserGroup

class ProfileView(APIView):
    def get(self, request):
        try:
            user = request.user
            
            # Check if user is authenticated
            if not user.is_authenticated:
                return Response({
                    'success': False,
                    'error_code': 'NOT_AUTHENTICATED',
                    'message': 'User is not authenticated.'
                }, status=status.HTTP_401_UNAUTHORIZED)
                
            # Make sure user is fully loaded
            # user = User.objects.get(pk=user.pk)
            
            serializer = UserSerializer(user)
            
            # Add debug information
            print(f"User data: {serializer.data}")
            
            return Response({
                'success': True,
                'data': {
                    'user': serializer.data,
                    'is_superuser': user.is_superuser
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # More detailed error logging
            import traceback
            print(f"Error in UserMeView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({    
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while processing the request: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user = request.user
            
            # Get data from request
            data = request.data
            
            # Update only specified fields
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'last_name' in data:
                user.last_name = data['last_name']
            if 'user_type' in data:
                user.user_type = data['user_type']
            
            # Handle avatar upload or deletion
            if 'avatar' in request.FILES:
                # Загружаем новый аватар
                user.avatar = request.FILES['avatar']
            elif 'avatar' in data:
                # Проверяем, нужно ли удалить аватар
                avatar_value = data['avatar']
                if avatar_value is None or avatar_value == '' or avatar_value == 'null':
                    # Удаляем аватар
                    user.avatar = None
            
            # Save changes
            user.save()
            
            # Serialize updated user data
            serializer = UserSerializer(user)
            
            return Response({
                'success': True,
                'data': {
                    'user': serializer.data,
                    'message': 'Profile updated successfully'
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Detailed error logging
            import traceback
            print(f"Error in ProfileUpdateView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while updating profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user = request.user
            data = request.data
            print(data)
            
            # Check required fields
            if 'current_password' not in data or 'new_password' not in data:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_FIELDS',
                    'message': 'Current and new password are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify current password
            if not user.check_password(data['current_password']):
                return Response({
                    'success': False,
                    'error_code': 'INVALID_PASSWORD',
                    'message': 'Current password is incorrect'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set new password
            user.set_password(data['new_password'])
            user.save()
            
            return Response({
                'success': True,
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Detailed error logging
            import traceback
            print(f"Error in PasswordChangeView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while changing password: {str(e)}'
            }, status.HTTP_500_INTERNAL_SERVER_ERROR)


class DigestSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получение настроек дайджеста пользователя"""
        try:
            from notifications.models import DigestSettings
            
            # Get or create digest settings for the user
            digest_settings, created = DigestSettings.objects.get_or_create(
                user=request.user,
                defaults={
                    'is_enabled': False,
                    'digest_hour': 8,
                    'timezone': 'America/New_York',
                    'additional_emails': [],
                    'custom_filters_enabled': False,
                    'custom_investors_enabled': False,
                    'custom_folders_enabled': False,
                }
            )
            
            return Response({
                'is_enabled': digest_settings.is_enabled,
                'digest_hour': digest_settings.digest_hour,
                'timezone': digest_settings.timezone,
                'additional_emails': digest_settings.additional_emails,
                'custom_filters_enabled': digest_settings.custom_filters_enabled,
                'custom_investors_enabled': digest_settings.custom_investors_enabled,
                'custom_folders_enabled': digest_settings.custom_folders_enabled
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in DigestSettingsView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'error': 'An error occurred while retrieving digest settings'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Обновление настроек дайджеста пользователя"""
        try:
            from notifications.models import DigestSettings
            from profile.models import SavedFilter, SavedParticipant, UserFolder
            
            # Get or create digest settings for the user
            digest_settings, created = DigestSettings.objects.get_or_create(
                user=request.user,
                defaults={
                    'is_enabled': False,
                    'digest_hour': 8,
                    'timezone': 'America/New_York',
                    'additional_emails': [],
                    'custom_filters_enabled': False,
                    'custom_investors_enabled': False,
                    'custom_folders_enabled': False,
                }
            )
            
            data = request.data
            
            # Update basic settings
            if 'is_enabled' in data:
                digest_settings.is_enabled = data['is_enabled']
            if 'digest_hour' in data:
                digest_settings.digest_hour = data['digest_hour']
            if 'timezone' in data:
                digest_settings.timezone = data['timezone']
            if 'additional_emails' in data:
                digest_settings.additional_emails = data['additional_emails']
            if 'custom_filters_enabled' in data:
                digest_settings.custom_filters_enabled = data['custom_filters_enabled']
            if 'custom_investors_enabled' in data:
                digest_settings.custom_investors_enabled = data['custom_investors_enabled']
            if 'custom_folders_enabled' in data:
                digest_settings.custom_folders_enabled = data['custom_folders_enabled']
            
            # Save basic settings
            digest_settings.save()
            
            # Update custom filters if provided
            if 'filters' in data and digest_settings.custom_filters_enabled:
                filters_data = data['filters']
                if isinstance(filters_data, list):
                    for filter_item in filters_data:
                        if 'id' in filter_item and 'in_digest' in filter_item:
                            SavedFilter.objects.filter(
                                user=request.user, 
                                id=filter_item['id']
                            ).update(in_digest=filter_item['in_digest'])
            
            # Update custom participants if provided
            if 'participants' in data and digest_settings.custom_investors_enabled:
                participants_data = data['participants']
                if isinstance(participants_data, list):
                    for participant_item in participants_data:
                        if 'id' in participant_item and 'in_digest' in participant_item:
                            SavedParticipant.objects.filter(
                                user=request.user, 
                                participant_id=participant_item['id']
                            ).update(in_digest=participant_item['in_digest'])
            
            # Update custom folders if provided
            if 'folders' in data and digest_settings.custom_folders_enabled:
                folders_data = data['folders']
                if isinstance(folders_data, list):
                    for folder_item in folders_data:
                        if 'id' in folder_item and 'in_digest' in folder_item:
                            UserFolder.objects.filter(
                                user=request.user, 
                                id=folder_item['id']
                            ).update(in_digest=folder_item['in_digest'])
            
            # Return updated settings
            return Response({
                'is_enabled': digest_settings.is_enabled,
                'digest_hour': digest_settings.digest_hour,
                'timezone': digest_settings.timezone,
                'additional_emails': digest_settings.additional_emails,
                'custom_filters_enabled': digest_settings.custom_filters_enabled,
                'custom_investors_enabled': digest_settings.custom_investors_enabled,
                'custom_folders_enabled': digest_settings.custom_folders_enabled
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in DigestSettingsView.post: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'error': 'An error occurred while updating digest settings'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OnboardingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Получить статус онбординга пользователя."""
        try:
            from profile.models import OnboardingStatus

            status_obj, _ = OnboardingStatus.objects.get_or_create(user=request.user)
            return Response({
                'status': status_obj.status,            # IN_PROGRESS | COMPLETED | SKIPPED | NONE
                'last_step_key': status_obj.last_step_key,
                'completed_at': status_obj.completed_at.isoformat() if status_obj.completed_at else None,
                'updated_at': status_obj.updated_at.isoformat() if status_obj.updated_at else None,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            print(f"Error in OnboardingStatusView.get: {str(e)}")
            print(traceback.format_exc())
            return Response({'error': 'Failed to fetch onboarding status'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Частично обновить статус онбординга и/или последний шаг.
        - status: IN_PROGRESS | COMPLETED | SKIPPED | NONE
        - last_step_key: string (ключ последнего шага)
        Если статус COMPLETED — выставляем completed_at (если не было).
        Если статус меняется с COMPLETED — не трогаем completed_at.
        """
        try:
            from profile.models import OnboardingStatus

            status_obj, _ = OnboardingStatus.objects.get_or_create(user=request.user)
            data = request.data

            new_status = data.get('status')
            last_step_key = data.get('last_step_key')

            if last_step_key is not None:
                status_obj.last_step_key = last_step_key

            if new_status in {"IN_PROGRESS", "COMPLETED", "SKIPPED", "DISABLED"}:
                # Если переход к COMPLETED и ранее не завершен — зафиксировать время
                if new_status == "COMPLETED" and status_obj.completed_at is None:
                    status_obj.completed_at = timezone.now()
                status_obj.status = new_status

            status_obj.save()

            return Response({
                'status': status_obj.status,
                'last_step_key': status_obj.last_step_key,
                'completed_at': status_obj.completed_at.isoformat() if status_obj.completed_at else None,
                'updated_at': status_obj.updated_at.isoformat() if status_obj.updated_at else None,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            print(f"Error in OnboardingStatusView.post: {str(e)}")
            print(traceback.format_exc())
            return Response({'error': 'Failed to update onboarding status'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserSavedFiltersView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получение сохраненных фильтров пользователя для настроек дайджеста"""
        try:
            from profile.models import SavedFilter
            
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            limit = 20  # Fixed limit as requested
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get user's saved filters
            filters = SavedFilter.objects.filter(user=request.user).order_by('-updated_at')
            
            total_count = filters.count()
            filters = filters[offset:offset + limit]
            
            # Serialize filters with basic info only
            filters_data = []
            for filter_obj in filters:
                filters_data.append({
                    'id': filter_obj.id,
                    'name': filter_obj.name,
                    'in_digest': filter_obj.in_digest
                })
            
            return Response({
                'filters': filters_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_count': total_count,
                    'has_next': offset + limit < total_count,
                    'has_previous': page > 1
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in UserSavedFiltersView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'error': 'An error occurred while retrieving saved filters'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserSavedParticipantsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получение сохраненных участников пользователя для настроек дайджеста"""
        try:
            from profile.models import SavedParticipant
            
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            limit = 20  # Fixed limit as requested
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get user's saved participants with participant data
            saved_participants = SavedParticipant.objects.filter(
                user=request.user
            ).select_related('participant').order_by('-id')
            
            total_count = saved_participants.count()
            saved_participants = saved_participants[offset:offset + limit]
            
            # Serialize participants
            participants_data = []
            for saved_participant in saved_participants:
                participant = saved_participant.participant
                participants_data.append({
                    'id': participant.id,
                    'name': participant.name,
                    'type': participant.type,
                    'image': participant.image.url if participant.image else None,
                    'about': participant.about,
                    'in_digest': saved_participant.in_digest
                })
            
            return Response({
                'participants': participants_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_count': total_count,
                    'has_next': offset + limit < total_count,
                    'has_previous': page > 1
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in UserSavedParticipantsView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'error': 'An error occurred while retrieving saved participants'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserFoldersView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получение папок пользователя для настроек дайджеста"""
        try:
            from profile.models import UserFolder
            
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            limit = 20  # Fixed limit as requested
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get user's folders
            folders = UserFolder.objects.filter(user=request.user).order_by('-created_at')
            
            total_count = folders.count()
            folders = folders[offset:offset + limit]
            
            # Serialize folders
            folders_data = []
            for folder in folders:
                folders_data.append({
                    'id': folder.id,
                    'name': folder.name,
                    'in_digest': folder.in_digest
                })
            
            return Response({
                'folders': folders_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_count': total_count,
                    'has_next': offset + limit < total_count,
                    'has_previous': page > 1
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in UserFoldersView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'error': 'An error occurred while retrieving user folders'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserGroupUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Обновление фото и имени группы пользователя.
        Пользователь может обновить только свою группу.
        """
        try:
            user = request.user
            
            # Проверяем, что у пользователя есть группа
            if not hasattr(user, 'group') or not user.group:
                return Response({
                    'success': False,
                    'error_code': 'NO_GROUP',
                    'message': 'Пользователь не состоит в группе'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            group = user.group
            data = request.data
            
            # Обновляем имя группы (если указано)
            if 'name' in data:
                new_name = data['name'].strip()
                if not new_name:
                    return Response({
                        'success': False,
                        'error_code': 'INVALID_NAME',
                        'message': 'Имя группы не может быть пустым'
                    }, status=status.HTTP_400_BAD_REQUEST)
                group.name = new_name
                # Slug обновится автоматически в save() методе модели
            
            # Обрабатываем загрузку или удаление логотипа
            if 'logo' in request.FILES:
                # Загружаем новый логотип
                group.logo = request.FILES['logo']
            elif 'logo' in data:
                # Проверяем, нужно ли удалить логотип
                logo_value = data['logo']
                if logo_value is None or logo_value == '' or logo_value == 'null':
                    # Удаляем логотип
                    group.logo = None
            
            # Сохраняем изменения
            group.save()
            
            # Сериализуем обновленную группу
            serializer = UserGroupSerializer(group)
            
            return Response({
                'success': True,
                'data': {
                    'group': serializer.data,
                    'message': 'Группа успешно обновлена'
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(f"Error in UserGroupUpdateView: {str(e)}")
            print(traceback.format_exc())
            
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'Произошла ошибка при обновлении группы: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)