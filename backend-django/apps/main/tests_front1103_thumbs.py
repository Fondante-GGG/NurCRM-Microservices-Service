"""03.11 front-market: миниатюры фото товаров (ProductImage.thumb, image_thumb_url, make_product_thumbs)."""
import io
import shutil
import tempfile
import uuid
from decimal import Decimal
from io import StringIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.main.models import Product, ProductImage
from apps.users.models import Company, User

MEDIA = tempfile.mkdtemp(prefix="thumbs1103-")


def jpeg(w=1600, h=1200, name="big.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(200, 30, 30)).save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA)
class ProductThumbTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        s = uuid.uuid4().hex[:6]
        self.owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner")
        self.company = Company.objects.create(name=f"Th {s}", owner=self.owner)
        self.owner.company = self.company
        self.owner.save()
        self.product = Product.objects.create(company=self.company, name="Кола", price=Decimal("100"))
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def test_upload_makes_320_webp_thumb_and_api_returns_it(self):
        r = self.api.post(f"/api/main/products/{self.product.id}/images/", {"image": jpeg(), "is_primary": "true"}, format="multipart")
        self.assertIn(r.status_code, (200, 201), getattr(r, "data", None))
        img = ProductImage.objects.get(product=self.product)
        self.assertTrue(img.thumb.name.endswith(".webp"))
        self.assertIn("/thumbs/", img.thumb.name)
        with Image.open(img.thumb.path) as t:
            self.assertEqual(t.format, "WEBP")
            self.assertEqual(t.size, (320, 240))
        self.assertTrue(str(r.data["image_thumb_url"]).endswith(img.thumb.name.split("/")[-1]))

        rows = self.api.get("/api/main/products/list/").data
        rows = rows["results"] if isinstance(rows, dict) else rows
        row = next(x for x in rows if str(x["id"]) == str(self.product.id))
        self.assertTrue(row["images"][0]["image_thumb_url"])
        self.assertTrue(row["images"][0]["image_url"])

        # удаление фото убирает и миниатюру
        path = img.thumb.path
        img.delete()
        import os
        self.assertFalse(os.path.exists(path))

    def test_small_image_not_enlarged_and_command_backfills(self):
        img = ProductImage.objects.create(company=self.company, product=self.product, image=jpeg(100, 50, "s.jpg"))
        with Image.open(img.thumb.path) as t:
            self.assertEqual(t.size, (100, 50))
        # старое фото без миниатюры
        ProductImage.objects.filter(pk=img.pk).update(thumb=None)
        out = StringIO()
        call_command("make_product_thumbs", "--dry-run", stdout=out)
        self.assertIn("фото без миниатюры: 1", out.getvalue())
        self.assertFalse(ProductImage.objects.get(pk=img.pk).thumb)
        out = StringIO()
        call_command("make_product_thumbs", "--sleep", "0", "--batch", "1", stdout=out)
        self.assertIn("сделано 1", out.getvalue())
        again = ProductImage.objects.get(pk=img.pk)
        self.assertTrue(again.thumb)
        self.assertEqual(again.image.name, img.image.name)  # оригинал не тронут
        out = StringIO()
        call_command("make_product_thumbs", stdout=out)
        self.assertIn("фото без миниатюры: 0", out.getvalue())

    def test_missing_file_skipped(self):
        img = ProductImage.objects.create(company=self.company, product=self.product, image=jpeg(10, 10, "m.jpg"))
        ProductImage.objects.filter(pk=img.pk).update(thumb=None, image="products/nope/missing.webp")
        out = StringIO()
        call_command("make_product_thumbs", "--sleep", "0", stdout=out, stderr=StringIO())
        self.assertIn("пропущено (нет файла / битый) 1", out.getvalue())
