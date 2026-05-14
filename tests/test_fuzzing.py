import random
import string

from tests.helpers import ApiCase


class FuzzingTest(ApiCase):
    def test_fuzz_invalid_roles_and_crud_payloads_do_not_crash(self):
        random.seed(42)
        alphabet = string.ascii_letters + string.digits + "-_{}[]@."
        endpoints = [
            ("POST", "/api/users", self.admin),
            ("POST", "/api/channels", self.admin),
            ("POST", "/api/integrations", self.admin),
            ("POST", "/api/channels/1/messages", self.alice),
        ]
        for index in range(80):
            word = "".join(random.choice(alphabet) for _ in range(random.randint(0, 32)))
            payload = {
                "email": f"{word}@corp.test",
                "name": word,
                "password": word,
                "role": random.choice(["admin", "moderator", "member", "bot", "owner", "", word]),
                "slug": word.lower(),
                "description": word,
                "is_private": random.choice([True, False, "true", None, 1]),
                "channel_id": random.choice([1, 999, "bad", 0]),
                "type": random.choice(["webhook", "git", "ci", "calendar", "sms", word]),
                "config": random.choice([{}, {"value": word}, "{}", "[]", word]),
                "enabled": random.choice([True, False, "yes", None]),
                "body": word,
            }
            method, path, token = endpoints[index % len(endpoints)]
            status, data, _ = self.request(method, path, token=token, payload=payload)
            self.assertLess(status, 500)
            if status >= 400:
                self.assertIn("error", data)

    def test_fuzz_malformed_json_and_auth_headers_do_not_crash(self):
        random.seed(7)
        for index in range(40):
            raw = bytes(random.randint(1, 255) for _ in range(index % 17))
            status, data, _ = self.request("POST", "/api/auth/login", raw_body=raw)
            self.assertLess(status, 500)
        for token in ["", "Bearer broken", "Token abc", "Bearer a.b.c"]:
            status, data, _ = self.request("GET", "/api/auth/me", headers={"Authorization": token})
            self.assertLess(status, 500)
