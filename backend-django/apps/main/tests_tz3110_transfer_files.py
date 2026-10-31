"""ТЗ 31.10 п.22: документы перемещения (stock/transfers/{id}/file/) и document_number."""
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from apps.main.models import MarketStockTransfer, Warehouse
from apps.main.tests_kassa_api import KassaBase

PDF = b"%PDF-1.4\n" + b"0" * 64


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StockTransferFilesTests(KassaBase):
    def make(self, **extra):
        wh = Warehouse.objects.create(company=self.company, name="Склад")
        body = {"from": None, "to": str(wh.id), "items": [{"product": str(self.product.id), "qty": "5"}], **extra}
        r = self.api.post("/api/main/stock-transfers/", body, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.json()

    def test_document_number_in_create_and_card(self):
        t = self.make(document_number="ПМ-17")
        self.assertEqual(t["document_number"], "ПМ-17")
        self.assertEqual(t["attachments"], [])
        card = self.api.get(f"/api/main/stock/transfers/{t['id']}/").json()
        self.assertEqual(card["document_number"], "ПМ-17")
        r = self.api.patch(f"/api/main/stock/transfers/{t['id']}/", {"document_number": "ПМ-18"}, format="json")
        self.assertEqual(r.json()["document_number"], "ПМ-18")

    def test_file_upload_list_delete(self):
        t = self.make()
        url = f"/api/main/stock/transfers/{t['id']}/file/"
        r = self.api.post(url, {"file": SimpleUploadedFile("n.pdf", PDF)}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        att = r.json()["attachments"][0]
        for key in ("id", "url", "size", "content_type", "sha256", "created_at", "document_type"):
            self.assertIn(key, att)
        self.assertEqual(len(self.api.get(url).json()["attachments"]), 1)
        card = self.api.get(f"/api/main/stock/transfers/{t['id']}/").json()
        self.assertEqual(len(card["attachments"]), 1)
        bad = self.api.post(url, {"file": SimpleUploadedFile("x.exe", b"MZ" + b"0" * 30)}, format="multipart")
        self.assertEqual((bad.status_code, bad.json()["code"]), (400, "invalid_type"))
        r = self.api.delete(f"{url}{att['id']}/")
        self.assertEqual(r.json()["attachments"], [])

    def test_other_company_gets_404(self):
        t = self.make()
        from apps.main.tests_tz_n32_media_receipts import _mk_company

        o2, _ = _mk_company("Чужой", "tz3110-tr-other")
        a2 = APIClient()
        a2.force_authenticate(o2)
        r = a2.post(f"/api/main/stock/transfers/{t['id']}/file/", {"file": SimpleUploadedFile("n.pdf", PDF)},
                    format="multipart")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(MarketStockTransfer.objects.count(), 1)
