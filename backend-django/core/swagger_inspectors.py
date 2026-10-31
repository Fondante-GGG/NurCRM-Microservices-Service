"""Инспекторы drf-yasg: чтобы схема OpenAPI (swagger/?format=openapi) генерировалась.

ТЗ 31.10 п.15: в проекте много сериализаторов с одинаковыми именами в разных
приложениях (например PayoutSerializer в barber и main). drf-yasg требует
уникальный ref_name и падает с SwaggerGenerationError. Здесь при коллизии имени
к ref_name добавляется префикс приложения.
"""
from drf_yasg.inspectors import ReferencingSerializerInspector
from drf_yasg.utils import get_serializer_ref_name


class UniqueRefNameSerializerInspector(ReferencingSerializerInspector):
    # базовое имя -> класс, который его занял первым
    _owners = {}

    def get_serializer_ref_name(self, serializer):
        ref_name = get_serializer_ref_name(serializer)
        if not ref_name:
            return ref_name
        meta = getattr(serializer, 'Meta', None)
        if hasattr(meta, 'ref_name'):
            return ref_name  # явное имя не трогаем
        cls = type(serializer)
        owner = self._owners.setdefault(ref_name, cls)
        if owner is cls:
            return ref_name
        parts = cls.__module__.split('.')
        prefix = '_'.join(p for p in parts if p not in ('apps', 'serializers', 'api'))
        return f'{prefix}_{ref_name}'


from drf_yasg.renderers import OpenAPIRenderer  # noqa: E402


class OpenAPIJsonRenderer(OpenAPIRenderer):
    """`?format=openapi` с заголовком Accept: application/json (иначе 406)."""
    media_type = 'application/json'
    format = 'openapi'
