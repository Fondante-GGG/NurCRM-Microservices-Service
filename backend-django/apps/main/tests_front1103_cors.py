"""03.11 front-market: CORS для фронта на Vercel и market.nurcrm.kg (заголовки запроса и ответа)."""
from django.test import TestCase


class FrontMarketCorsTests(TestCase):
    def _preflight(self, origin, headers):
        return self.client.options(
            "/api/main/capabilities/", HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
        )

    def test_vercel_preview_and_market_allowed_with_headers(self):
        for origin in ("https://front-market.vercel.app", "https://front-market-git-x-umar.vercel.app", "https://market.nurcrm.kg"):
            r = self._preflight(origin, "authorization,content-type,idempotency-key,x-nurmarket-client,x-pin-token,if-match")
            self.assertEqual(r.headers.get("access-control-allow-origin"), origin)
            allowed = r.headers.get("access-control-allow-headers", "").lower()
            for h in ("authorization", "idempotency-key", "x-nurmarket-client", "x-pin-token", "if-match"):
                self.assertIn(h, allowed)

    def test_expose_retry_after(self):
        r = self.client.get("/api/main/capabilities/", HTTP_ORIGIN="https://front-market.vercel.app")
        self.assertIn("retry-after", r.headers.get("access-control-expose-headers", "").lower())
