"""Billing-shape tests: monthly checkout carries the 14-day trial; /pricing says so."""

import http.client
import pathlib
import tempfile
import threading
import unittest
import urllib.request

from agentrust import web


class BillingTests(unittest.TestCase):
    def _server(self, t):
        env = {
            "STRIPE_SECRET_KEY": "sk_test_x",
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "STRIPE_PRICES": "developer=price_123,growth=price_456,enterprise=price_789",
            "PUBLIC_URL": "https://example.test",
        }
        srv = web.make_server("127.0.0.1", 0, pathlib.Path(t), env=env)
        return srv

    def test_monthly_checkout_is_subscription_with_14_day_trial(self):
        with tempfile.TemporaryDirectory() as t:
            srv = self._server(t)
            billing = srv.RequestHandlerClass.billing
            sent = {}
            billing._stripe = lambda path, form: sent.update(form) or {"url": "https://checkout.test/s"}
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=30)
                conn.request("POST", "/billing/checkout", "plan=developer")
                res = conn.getresponse()
                self.assertEqual(res.status, 303)
                self.assertEqual(res.getheader("Location"), "https://checkout.test/s")
                conn.close()
            finally:
                srv.shutdown()
            self.assertEqual(sent["mode"], "subscription")
            self.assertEqual(sent["subscription_data[trial_period_days]"], "14")
            self.assertEqual(sent["line_items[0][price]"], "price_123")

    def test_pricing_page_notes_trial_when_billing_enabled(self):
        with tempfile.TemporaryDirectory() as t:
            srv = self._server(t)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                base = f"http://127.0.0.1:{srv.server_address[1]}"
                body = urllib.request.urlopen(base + "/pricing", timeout=30).read()
            finally:
                srv.shutdown()
            self.assertIn(b"14-day free trial", body)
            self.assertIn(b"Subscribe", body)


if __name__ == "__main__":
    unittest.main()
