import unittest

from server.httpd import CLIENT_DIR, resolve_static_target, static_content_type


class StaticHttpTest(unittest.TestCase):
    def test_resolves_root_to_index_html(self):
        self.assertEqual(resolve_static_target("/"), CLIENT_DIR / "index.html")
        self.assertEqual(resolve_static_target("/missing-route"), CLIENT_DIR / "index.html")

    def test_rejects_path_traversal(self):
        self.assertIsNone(resolve_static_target("/../server/app.py"))

    def test_content_types(self):
        self.assertEqual(static_content_type(CLIENT_DIR / "index.html"), "text/html; charset=utf-8")
        self.assertEqual(static_content_type(CLIENT_DIR / "styles.css"), "text/css; charset=utf-8")
        self.assertEqual(static_content_type(CLIENT_DIR / "app.js"), "application/javascript; charset=utf-8")
        self.assertEqual(static_content_type(CLIENT_DIR / "unknown.txt"), "text/plain; charset=utf-8")
