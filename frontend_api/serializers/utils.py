from django.conf import settings

def build_absolute_image_url(model_instance, absolute_image_url=False, field_name='image', base_url=settings.BASE_IMAGE_URL):
    if hasattr(model_instance, field_name) and getattr(model_instance, field_name):
        image_url = getattr(model_instance, field_name).url
        if absolute_image_url:
            image_url = base_url.rstrip("/") + "/" + image_url.lstrip("/")
        return image_url
    return None
