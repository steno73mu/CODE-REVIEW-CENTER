import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from review_core.configuration import ProviderConfigStore, ProviderProfile
from review_core.finding import Finding, FindingSeverity
from review_core.providers import AIReviewClient, AIReviewError


class _ProviderHandler(BaseHTTPRequestHandler):
    request_payload = None
    authorization = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).request_payload = json.loads(self.rfile.read(length))
        type(self).authorization = self.headers.get("Authorization")
        body = json.dumps({
            "choices": [{"message": {"content": "Review summary: investigate the finding."}}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class ProviderIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _ProviderHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def setUp(self):
        self.profile = ProviderProfile(
            provider_id="local-model",
            name="Local model",
            base_url=self.base_url,
            model="local-review-model",
            api_key_env="CRC_TEST_PROVIDER_KEY",
            timeout_seconds=5,
        )
        os.environ["CRC_TEST_PROVIDER_KEY"] = "test-secret-key"

    def tearDown(self):
        os.environ.pop("CRC_TEST_PROVIDER_KEY", None)

    def test_sends_findings_to_openai_compatible_local_endpoint(self):
        finding = Finding(
            tool="Semgrep",
            message="Unsafe deserialization",
            severity=FindingSeverity.HIGH,
            path="src/app.py",
            start_line=10,
        )
        result = AIReviewClient().review_findings(self.profile, [finding])

        self.assertIn("investigate", result.content)
        self.assertEqual(_ProviderHandler.authorization, "Bearer test-secret-key")
        serialized = json.dumps(_ProviderHandler.request_payload)
        self.assertIn("Unsafe deserialization", serialized)
        self.assertNotIn("test-secret-key", serialized)

    def test_requires_explicit_opt_in_for_remote_providers(self):
        remote = ProviderProfile(
            "remote", "Remote", "https://api.example.com/v1", "model", None, 5
        )
        with self.assertRaises(AIReviewError):
            AIReviewClient().review_findings(remote, [])

    def test_rejects_plain_http_for_non_loopback_provider(self):
        with self.assertRaises(ValueError):
            ProviderProfile("remote", "Remote", "http://api.example.com/v1", "model", None, 5)

    def test_rejects_embedded_credentials_and_invalid_api_key_reference(self):
        for url, key_ref in (
            ("https://user:pass@example.com/v1", None),
            ("https://example.com/v1", "actual-secret-value"),
        ):
            with self.subTest(url=url, key_ref=key_ref):
                with self.assertRaises(ValueError):
                    ProviderProfile("bad", "Bad", url, "model", key_ref, 5)

    def test_provider_store_persists_environment_variable_name_not_secret(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            store = ProviderConfigStore(Path(directory) / "providers.sqlite3")
            store.save(self.profile)
            loaded = store.get("local-model")
            self.assertEqual(loaded, self.profile)
            raw = (Path(directory) / "providers.sqlite3").read_bytes()
            self.assertNotIn(b"test-secret-key", raw)

    def test_missing_api_key_environment_variable_is_reported_safely(self):
        os.environ.pop("CRC_TEST_PROVIDER_KEY", None)
        with self.assertRaises(AIReviewError):
            AIReviewClient().review_findings(self.profile, [])


if __name__ == "__main__":
    unittest.main()
