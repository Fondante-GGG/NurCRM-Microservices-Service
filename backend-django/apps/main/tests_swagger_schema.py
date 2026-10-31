"""ТЗ 31.10 п.15: схема OpenAPI должна генерироваться (раньше SwaggerGenerationError)."""
from django.test import SimpleTestCase

from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator

from core.swagger_renderers import OpenAPIJsonRenderer


class SwaggerSchemaTests(SimpleTestCase):
    def test_schema_generates(self):
        from core.swagger_inspectors import use_unique_ref_names

        use_unique_ref_names()  # как в core/urls.py при ENABLE_API_DOCS
        gen = OpenAPISchemaGenerator(openapi.Info(title="Nur CRM API", default_version="v1"))
        schema = gen.get_schema(request=None, public=True)
        self.assertGreater(len(schema["paths"]), 100)

    def test_openapi_renderer_accepts_application_json(self):
        self.assertEqual(OpenAPIJsonRenderer.format, "openapi")
        self.assertEqual(OpenAPIJsonRenderer.media_type, "application/json")

    def test_settings_do_not_import_project_modules(self):
        # 31.10: инспектор в SWAGGER_SETTINGS давал круговой импорт на сервере (ENABLE_API_DOCS=True)
        from django.conf import settings
        self.assertNotIn("DEFAULT_FIELD_INSPECTORS", settings.SWAGGER_SETTINGS)
