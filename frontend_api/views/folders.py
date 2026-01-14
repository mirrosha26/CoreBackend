from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
import json
import csv
from datetime import datetime

from profile.models import UserFolder, FolderCard
from signals.models import SignalCard, STAGES, ROUNDS
from frontend_api.serializers.cards.previews import serialize_previews
from signals.utils import get_image_url


class FolderListView(APIView):
    """
    API представление для работы со списком папок пользователя.
    GET - получение списка папок
    POST - создание новой папки
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        try:
            # Получаем все папки пользователя с количеством карточек в каждой
            folders = UserFolder.objects.filter(user=request.user)\
                .annotate(cards_count=Count('folder_cards'))\
                .values('id', 'name', 'description', 'is_default', 'created_at', 'updated_at', 'cards_count')
            
            # Преобразуем даты в строки для корректной сериализации JSON
            folders_list = list(folders)
            for folder in folders_list:
                folder['created_at'] = folder['created_at'].isoformat()
                folder['updated_at'] = folder['updated_at'].isoformat()
                # Добавляем folder_key в зависимости от is_default
                folder['folder_key'] = 'default' if folder['is_default'] else str(folder['id'])
            
            return Response({
                'success': True,
                'folders': folders_list
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, *args, **kwargs):
        try:
            name = request.data.get('name')
            description = request.data.get('description', '')
            is_default = request.data.get('is_default', False)
            
            if not name:
                return Response({
                    'success': False,
                    'error': 'MISSING_NAME',
                    'message': 'Название папки обязательно'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Создаем новую папку
            folder = UserFolder.objects.create(
                user=request.user,
                name=name,
                description=description,
                is_default=is_default
            )
            
            return Response({
                'success': True,
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'description': folder.description,
                    'is_default': folder.is_default,
                    'created_at': folder.created_at.isoformat(),
                    'updated_at': folder.updated_at.isoformat(),
                    'cards_count': 0,
                    'folder_key': 'default' if folder.is_default else str(folder.id)
                }
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({
                'success': False,
                'error': 'DUPLICATE_NAME',
                'message': 'Папка с таким названием уже существует'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FolderDetailView(APIView):
    """
    API представление для работы с конкретной папкой.
    GET - получение информации о папке
    PUT - обновление папки
    DELETE - удаление папки
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, folder_id, *args, **kwargs):
        try:
            folder = get_object_or_404(UserFolder, id=folder_id, user=request.user)
            
            return Response({
                'success': True,
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'description': folder.description,
                    'is_default': folder.is_default,
                    'created_at': folder.created_at.isoformat(),
                    'updated_at': folder.updated_at.isoformat(),
                    'cards_count': folder.folder_cards.count()
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, folder_id, *args, **kwargs):
        try:
            name = request.data.get('name')
            description = request.data.get('description')
            
            if not name:
                return Response({
                    'success': False,
                    'error': 'MISSING_NAME',
                    'message': 'Название папки обязательно'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            folder = get_object_or_404(UserFolder, id=folder_id, user=request.user)
            
            # Обновляем данные папки
            folder.name = name
            if description is not None:
                folder.description = description
            
            folder.save()
            
            return Response({
                'success': True,
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'description': folder.description,
                    'is_default': folder.is_default,
                    'created_at': folder.created_at.isoformat(),
                    'updated_at': folder.updated_at.isoformat(),
                    'cards_count': folder.folder_cards.count()
                }
            }, status=status.HTTP_200_OK)
        except IntegrityError:
            return Response({
                'success': False,
                'error': 'DUPLICATE_NAME',
                'message': 'Папка с таким названием уже существует'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, folder_id, *args, **kwargs):
        try:
            folder = get_object_or_404(UserFolder, id=folder_id, user=request.user)
            
            # Проверяем, является ли папка папкой по умолчанию
            if folder.is_default:
                return Response({
                    'success': False,
                    'error': 'DEFAULT_FOLDER',
                    'message': 'Нельзя удалить папку по умолчанию'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            folder.delete()
            return Response({
                'success': True,
                'message': 'Папка успешно удалена'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CardFoldersView(APIView):
    """
    API представление для работы с папками карточки.
    GET - получение списка папок для карточки
    POST - обновление папок карточки
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id, *args, **kwargs):
        try:
            # Проверяем существование карточки
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Получаем все папки пользователя
            user_folders = UserFolder.objects.filter(user=request.user)
            
            # Получаем папки, в которых находится данная карточка
            card_folder_ids = FolderCard.objects.filter(
                signal_card_id=card_id,
                folder__user=request.user
            ).values_list('folder_id', flat=True)
            
            # Формируем список папок с флагом наличия карточки
            folders_data = []
            for folder in user_folders:
                folders_data.append({
                    'id': folder.id,
                    'name': folder.name,
                    'is_default': folder.is_default,
                    'has_card': folder.id in card_folder_ids
                })
            
            return Response({
                'success': True,
                'folders': folders_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, card_id, *args, **kwargs):
        try:
            # Проверяем существование карточки
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            include_folders = request.data.get('include_folders', [])
            exclude_folders = request.data.get('exclude_folders', [])
            
            # Проверяем, что папки принадлежат пользователю
            user_folder_ids = set(UserFolder.objects.filter(
                user=request.user
            ).values_list('id', flat=True))
            
            for folder_id in include_folders + exclude_folders:
                if folder_id not in user_folder_ids:
                    return Response({
                        'success': False,
                        'error': 'FORBIDDEN',
                        'message': f'Папка {folder_id} не принадлежит пользователю'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Добавляем карточку в указанные папки
            for folder_id in include_folders:
                FolderCard.objects.get_or_create(
                    folder_id=folder_id,
                    signal_card=signal_card
                )
            
            # Удаляем карточку из указанных папок
            FolderCard.objects.filter(
                folder_id__in=exclude_folders,
                signal_card=signal_card
            ).delete()
            
            # Если карточка добавляется хотя бы в одну папку, удаляем её из списка удаленных
            if include_folders:
                from profile.models import DeletedCard
                DeletedCard.objects.filter(user=request.user, signal_card_id=card_id).delete()
            
            return Response({
                'success': True,
                'message': 'Папки карточки обновлены'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FolderExportView(APIView):
    """
    API представление для экспорта папки в CSV файл.
    GET - экспорт всех проектов в папке в CSV
    
    Поддерживает следующие режимы:
    1. /folders/export/?folder={id} - экспорт из конкретной папки по ID
    2. /folders/export/?folder=favorites - экспорт из папки по умолчанию (избранное)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, folder_id=None, *args, **kwargs):
        try:
            # Получаем базовый URL для абсолютных URL
            base_url = request.build_absolute_uri('/').rstrip('/')
            
            # Создаем словари для поиска стадий и раундов
            STAGES_DICT = dict(STAGES)
            ROUNDS_DICT = dict(ROUNDS)
            
            # Определяем папку для экспорта
            folder = None
            folder_name = None
            
            # Проверяем параметр folder из query string
            folder_param = request.query_params.get('folder')
            
            if folder_param:
                if folder_param.lower() == 'favorites':
                    # Экспорт избранных проектов (папка по умолчанию)
                    folder = get_object_or_404(UserFolder, user=request.user, is_default=True)
                    folder_name = "Favorites"
                else:
                    # Экспорт конкретной папки по ID
                    try:
                        folder_id_from_param = int(folder_param)
                        folder = get_object_or_404(UserFolder, id=folder_id_from_param, user=request.user)
                        folder_name = folder.name
                    except ValueError:
                        return Response({
                            'success': False,
                            'error': 'INVALID_FOLDER_PARAMETER',
                            'message': 'Параметр folder должен быть числом или "favorites"'
                        }, status=status.HTTP_400_BAD_REQUEST)
            elif folder_id:
                # Обратная совместимость: экспорт по folder_id из URL
                folder = get_object_or_404(UserFolder, id=folder_id, user=request.user)
                folder_name = folder.name
            else:
                # Если не указан ни folder_id, ни параметр folder
                return Response({
                    'success': False,
                    'error': 'MISSING_FOLDER_PARAMETER',
                    'message': 'Необходимо указать параметр folder (ID папки или "favorites")'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем все карточки сигналов в этой папке с предзагруженными связанными данными
            folder_cards = FolderCard.objects.filter(folder=folder).select_related('signal_card').prefetch_related(
                'signal_card__categories',
                'signal_card__people',
                'signal_card__signals',
                'signal_card__signals__participant',
                'signal_card__signals__participant__associated_with',
                'signal_card__signals__source',
                'signal_card__tags'
            )
            
            # Создаем CSV ответ
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{folder_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            # Создаем CSV writer
            writer = csv.writer(response)
            
            # Записываем заголовок
            writer.writerow([
                'Name', 'Description', 'URL', 'Stage', 'Round Status', 
                'Reference URL', 'Location', 'Categories',  
                'Created At', 'Latest Signal Date', 
                'Number of Interactions', 'Image URL', 'Twitter URL', 
                'LinkedIn URL', 'Product Hunt URL', 'Crunchbase URL', 'Project URL'
            ])
            
            # Записываем данные
            for folder_card in folder_cards:
                card = folder_card.signal_card
                
                # Получаем категории как строку, разделенную запятыми
                categories = ', '.join([category.name for category in card.categories.all()])
                
                # Получаем стадию и статус раунда в удобном формате
                stage = STAGES_DICT.get(card.stage, 'Unknown')
                round_status = ROUNDS_DICT.get(card.round_status, 'Unknown')
                
                # Группируем инвесторов по их фондам
                fund_to_investors = {}
                independent_investors = []
                latest_signal_date = None
                
                for signal in card.signals.all():
                    if signal.participant:
                        # Обновляем дату последнего сигнала
                        if latest_signal_date is None or signal.created_at > latest_signal_date:
                            latest_signal_date = signal.created_at
                        
                        # Получаем имя инвестора
                        investor_name = signal.participant.name
                        
                        # Проверяем, существует ли участник и есть ли у него associated_with (фонд)
                        if signal.participant and hasattr(signal.participant, 'associated_with') and signal.participant.associated_with:
                            fund = signal.participant.associated_with
                            
                            # Пропускаем, если участник тот же, что и фонд (чтобы избежать дублирования)
                            if signal.participant.id == fund.id:
                                fund_name = fund.name
                                if fund_name not in fund_to_investors:
                                    fund_to_investors[fund_name] = []
                            else:
                                # Добавляем инвестора в группу его фонда
                                fund_name = fund.name
                                if fund_name not in fund_to_investors:
                                    fund_to_investors[fund_name] = []
                                if investor_name not in fund_to_investors[fund_name]:
                                    fund_to_investors[fund_name].append(investor_name)
                        else:
                            # Добавляем как независимого инвестора
                            if investor_name not in independent_investors:
                                independent_investors.append(investor_name)
                
                # Общее количество инвесторов (фонды + независимые инвесторы)
                total_investor_count = sum(len(investors) for investors in fund_to_investors.values()) + len(independent_investors)
                # Добавляем количество фондов без перечисленных инвесторов
                total_investor_count += sum(1 for investors in fund_to_investors.values() if len(investors) == 0)
                
                # Получаем URL социальных сетей и дополнительные данные
                twitter_url = ''
                linkedin_url = ''
                product_hunt_url = ''
                crunchbase_url = ''
                project_url = ''
                reference_url = card.reference_url or ''
                
                if card.more:
                    for item in card.more:
                        if isinstance(item, dict):
                            # Извлекаем из 'value', если он существует (для социальных ссылок)
                            if 'value' in item and isinstance(item['value'], dict):
                                if 'twitter' in item['value']:
                                    twitter_url = item['value']['twitter']
                                if 'linkedin' in item['value']:
                                    linkedin_url = item['value']['linkedin']
                                if 'producthunt' in item['value']:
                                    product_hunt_url = item['value']['producthunt']
                                if 'crunchbase' in item['value']:
                                    crunchbase_url = item['value']['crunchbase']
                                if 'reference_url' in item['value'] and not reference_url:
                                    reference_url = item['value']['reference_url']
                                if 'project_url' in item['value']:
                                    project_url = item['value']['project_url']
                            
                            # Прямые свойства
                            if 'twitter_url' in item:
                                twitter_url = item['twitter_url']
                            if 'linkedin_url' in item:
                                linkedin_url = item['linkedin_url']
                            if 'product_hunt_url' in item:
                                product_hunt_url = item['product_hunt_url']
                            if 'crunchbase_url' in item:
                                crunchbase_url = item['crunchbase_url']
                            if 'project_url' in item:
                                project_url = item['project_url']
                
                # Генерируем URL изображения
                image_url = get_image_url(card, absolute_image_url=True, base_url=base_url) if card.image else ""
                
                writer.writerow([
                    card.name,
                    card.description,
                    card.url,
                    stage,
                    round_status,
                    reference_url,
                    card.location,
                    categories,
                    card.created_at.strftime('%Y-%m-%d') if card.created_at else '',
                    latest_signal_date.strftime('%Y-%m-%d') if latest_signal_date else '',
                    total_investor_count,
                    image_url,
                    twitter_url,
                    linkedin_url,
                    product_hunt_url,
                    crunchbase_url,
                    project_url
                ])
            
            return response
            
        except UserFolder.DoesNotExist:
            return Response({
                'success': False,
                'error': 'FOLDER_NOT_FOUND',
                'message': 'Папка не найдена или у вас нет прав доступа к ней'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

