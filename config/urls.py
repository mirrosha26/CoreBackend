from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path
from django.http import JsonResponse

def error_404(request, exception):
    return JsonResponse({
        'error': 'not_found',
        'message': 'Resource not found'
    }, status=404)

def error_500(request):
    return JsonResponse({
        'error': 'internal_server_error',
        'message': 'Internal server error'
    }, status=500)

def error_403(request, exception):
    return JsonResponse({
        'error': 'permission_denied',
        'message': 'You do not have permission to perform this action'
    }, status=403)

def error_400(request, exception):
    return JsonResponse({
        'error': 'bad_request',
        'message': 'Bad request'
    }, status=400)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('s-api/', include('signals.urls')), 
    path('f-api/', include('frontend_api.urls')),
    path('graphql/', include('graphql_app.urls')),
    path('client_api/', include('client_api.urls')),
]

# Статические и медиафайлы
# Всегда обслуживаем медиафайлы (и при DEBUG=True, и при DEBUG=False)
# Добавляем медиафайлы в конец, чтобы они не перехватывали другие маршруты
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

# Статические файлы
if settings.DEBUG:
    # В режиме разработки используем STATICFILES_DIRS (папка static)
    if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        for static_dir in settings.STATICFILES_DIRS:
            urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
    else:
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # При DEBUG=False обслуживаем статические файлы из STATIC_ROOT (assets) через Django view
    # ВНИМАНИЕ: Для продакшена рекомендуется использовать веб-сервер (nginx/apache) или WhiteNoise для статических файлов
    # Используем STATIC_URL из settings и всегда берем файлы из STATIC_ROOT (assets)
    static_url_pattern = settings.STATIC_URL.lstrip('/')
    urlpatterns += [
        re_path(r'^{}(?P<path>.*)$'.format(static_url_pattern), serve, {'document_root': settings.STATIC_ROOT}),
    ]

handler404 = error_404
handler500 = error_500 
handler403 = error_403
handler400 = error_400