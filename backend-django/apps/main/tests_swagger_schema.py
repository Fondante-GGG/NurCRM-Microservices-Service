"""ТЗ 31.10 п.15: схема OpenAPI должна генерироваться (раньше SwaggerGenerationError)."""
from django.test import SimpleTestCase

from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator

from core.swagger_inspectors import OpenAPIJsonRenderer


class SwaggerSchemaTests(SimpleTestCase):
    def test_schema_generates(self):
        gen = OpenAPISchemaGenerator(openapi.Info(title="Nur CRM API", default_version="v1"))
        schema = gen.get_schema(request=None, public=True)
        self.assertGreater(len(schema["paths"]), 100)

    def test_openapi_renderer_accepts_application_json(self):
        self.assertEqual(OpenAPIJsonRenderer.format, "openapi")
        self.assertEqual(OpenAPIJsonRenderer.media_type, "application/json")
