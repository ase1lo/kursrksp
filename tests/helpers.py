import json
import unittest

from server.app import MessengerApp
from server.config import Settings


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.settings = Settings("test", "sqlite:///:memory:", "test-secret", 8080, 3600, "*")
        self.app = MessengerApp(self.settings)
        self.request("POST", "/api/seed")
        self.admin = self.login("admin@corp.test", "AdminPass123")
        self.moderator = self.login("mod@corp.test", "ModeratorPass123")
        self.alice = self.login("alice@corp.test", "AlicePass123")
        self.bot = self.login("deploy-bot@corp.test", "DeployBot123")

    def request(self, method, path, token=None, payload=None, raw_body=None, headers=None):
        request_headers = dict(headers or {})
        if token:
            request_headers["Authorization"] = "Bearer {}".format(token)
        if raw_body is not None:
            body = raw_body
        elif payload is None:
            body = b""
        else:
            body = json.dumps(payload).encode("utf-8")
        response = self.app.handle(method, path, request_headers, body)
        data = json.loads(response.body().decode("utf-8")) if response.body() else {}
        return response.status, data, response.headers

    def login(self, email, password):
        status, data, _ = self.request("POST", "/api/auth/login", payload={"email": email, "password": password})
        self.assertEqual(status, 200)
        return data["token"]

    def tearDown(self):
        self.app.db.close()
