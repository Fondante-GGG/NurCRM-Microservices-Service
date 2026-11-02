"""S7 (аудит 03.11): POST cashflows/{id}/check/ без поля checked не трогает отметку."""
from apps.construction.models import CashFlow
from apps.construction.tests_buhgalter import BuhBase


class CheckNoteOnlyTests(BuhBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.owner)
        self.fid = self.post_flow(amount="40.00").data["id"]
        self.url = f"/api/construction/cashflows/{self.fid}/check/"

    def test_note_only_keeps_unchecked(self):
        r = self.client.post(self.url, {"note": "спросить"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["checked"])
        f = CashFlow.objects.get(pk=self.fid)
        self.assertIsNone(f.checked_at)
        self.assertEqual(f.accountant_note, "спросить")

    def test_note_only_keeps_checked_and_author(self):
        self.client.force_authenticate(self.acc)
        self.client.post(self.url, {"checked": True}, format="json")
        before = CashFlow.objects.get(pk=self.fid)
        self.client.force_authenticate(self.owner)
        r = self.client.post(self.url, {"note": "ок"}, format="json")
        self.assertTrue(r.data["checked"])
        after = CashFlow.objects.get(pk=self.fid)
        self.assertEqual((after.checked_at, after.checked_by_id), (before.checked_at, self.acc.id))
        # повторное checked=true тоже не перезаписывает
        self.client.post(self.url, {"checked": True}, format="json")
        again = CashFlow.objects.get(pk=self.fid)
        self.assertEqual((again.checked_at, again.checked_by_id), (before.checked_at, self.acc.id))

    def test_empty_body_checks_as_before(self):
        r = self.client.post(self.url, {}, format="json")
        self.assertTrue(r.data["checked"])
        self.assertEqual(CashFlow.objects.get(pk=self.fid).checked_by_id, self.owner.id)
        r = self.client.post(self.url, {"checked": False, "note": ""}, format="json")
        self.assertFalse(r.data["checked"])
