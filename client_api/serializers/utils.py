from django.conf import settings


def build_absolute_image_url(model_instance, absolute_image_url=False, field_name='image', base_url=None):
    """
    Строит абсолютный URL для изображения модели.
    
    Args:
        model_instance: Экземпляр модели с полем image
        absolute_image_url: Если True, возвращает абсолютный URL
        field_name: Имя поля с изображением (по умолчанию 'image')
        base_url: Базовый URL (если не указан, используется из settings или дефолтный)
    
    Returns:
        str: URL изображения или None
    """
    if base_url is None:
        base_url = getattr(settings, 'BASE_URL', 'https://app.theveck.com')
        if not base_url.endswith('/'):
            base_url += '/'
    
    if hasattr(model_instance, field_name) and getattr(model_instance, field_name):
        image_field = getattr(model_instance, field_name)
        if image_field:
            image_url = image_field.url  # Относительный путь, например: /media/signalcard/...
            if absolute_image_url:
                # Убеждаемся, что base_url заканчивается на /, а image_url начинается с /
                base_url_clean = base_url.rstrip("/")
                image_url_clean = image_url.lstrip("/")
                image_url = f"{base_url_clean}/{image_url_clean}"
            return image_url
    return None

