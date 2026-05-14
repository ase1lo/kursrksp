from tests.helpers import ApiCase


class ApiWorkflowTest(ApiCase):
    def test_health_options_seed_and_auth_errors(self):
        status, data, headers = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIn("Access-Control-Allow-Origin", headers)
        status, data, _ = self.request("OPTIONS", "/api/channels")
        self.assertEqual(status, 204)
        self.assertEqual(data, {})
        status, data, _ = self.request("POST", "/api/seed")
        self.assertEqual(status, 201)
        self.assertFalse(data["seeded"])
        status, data, _ = self.request("GET", "/api/auth/me")
        self.assertEqual(status, 401)
        self.assertEqual(data["error"], "auth_error")
        status, data, _ = self.request("GET", "/api/auth/me", headers={"Authorization": "Token bad"})
        self.assertEqual(status, 401)
        status, data, _ = self.request("POST", "/api/auth/login", payload={"email": "bad@corp.test", "password": "badpass123"})
        self.assertEqual(status, 401)
        status, data, _ = self.request("POST", "/api/auth/login", raw_body=b"{bad")
        self.assertEqual(status, 400)
        status, data, _ = self.request("GET", "/api/unknown", token=self.admin)
        self.assertEqual(status, 404)

    def test_current_user_and_user_crud_with_role_validation(self):
        status, data, _ = self.request("GET", "/api/auth/me", token=self.admin)
        self.assertEqual(status, 200)
        self.assertEqual(data["user"]["role"], "admin")
        status, data, _ = self.request("GET", "/api/users", token=self.admin)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data["users"]), 4)
        status, data, _ = self.request(
            "POST",
            "/api/users",
            token=self.admin,
            payload={"email": "charlie@corp.test", "name": "Charlie", "password": "CharliePass123", "role": "member"},
        )
        self.assertEqual(status, 201)
        charlie_id = data["user"]["id"]
        status, data, _ = self.request("PATCH", f"/api/users/{charlie_id}", token=self.admin, payload={"name": "Charles", "role": "moderator", "active": True})
        self.assertEqual(status, 200)
        self.assertEqual(data["user"]["name"], "Charles")
        self.assertEqual(data["user"]["role"], "moderator")
        status, data, _ = self.request("DELETE", f"/api/users/{charlie_id}", token=self.admin)
        self.assertEqual(status, 200)
        status, data, _ = self.request(
            "POST",
            "/api/users",
            token=self.admin,
            payload={"email": "charlie@corp.test", "name": "Charlie", "password": "CharliePass123", "role": "member"},
        )
        self.assertEqual(status, 409)
        status, data, _ = self.request(
            "POST",
            "/api/users",
            token=self.admin,
            payload={"email": "bad-role@corp.test", "name": "Bad Role", "password": "Password123", "role": "owner"},
        )
        self.assertEqual(status, 400)
        status, data, _ = self.request("PATCH", "/api/users/1", token=self.admin, payload={"role": "owner"})
        self.assertEqual(status, 400)
        status, data, _ = self.request("PATCH", "/api/users/1", token=self.admin, payload={})
        self.assertEqual(status, 400)
        status, data, _ = self.request("GET", "/api/users", token=self.moderator)
        self.assertEqual(status, 403)
        status, data, _ = self.request("PATCH", "/api/users/abc", token=self.admin, payload={"name": "Nobody"})
        self.assertEqual(status, 404)

    def test_channel_message_and_membership_workflow(self):
        status, data, _ = self.request("GET", "/api/channels?q=eng", token=self.alice)
        self.assertEqual(status, 200)
        self.assertEqual(data["filter"], "eng")
        status, data, _ = self.request(
            "POST",
            "/api/channels",
            token=self.admin,
            payload={"slug": "release-room", "name": "Release Room", "description": "Private release work", "is_private": True},
        )
        self.assertEqual(status, 201)
        release_id = data["channel"]["id"]
        status, data, _ = self.request("GET", f"/api/channels/{release_id}/messages", token=self.alice)
        self.assertEqual(status, 401)
        status, data, _ = self.request("GET", "/api/users", token=self.admin)
        alice_id = next(user["id"] for user in data["users"] if user["email"] == "alice@corp.test")
        status, data, _ = self.request("POST", f"/api/channels/{release_id}/members", token=self.admin, payload={"user_id": alice_id})
        self.assertEqual(status, 201)
        status, data, _ = self.request("GET", f"/api/channels/{release_id}", token=self.alice)
        self.assertEqual(status, 200)
        status, data, _ = self.request("GET", f"/api/channels/{release_id}/messages", token=self.alice)
        self.assertEqual(status, 200)
        self.assertEqual(data["messages"], [])
        status, data, _ = self.request("POST", f"/api/channels/{release_id}/messages", token=self.alice, payload={"body": "Ready to ship"})
        self.assertEqual(status, 201)
        message_id = data["message"]["id"]
        status, data, _ = self.request("PATCH", f"/api/messages/{message_id}", token=self.alice, payload={"body": "Ready to ship safely"})
        self.assertEqual(status, 200)
        self.assertTrue(data["message"]["edited"])
        status, data, _ = self.request("PATCH", f"/api/channels/{release_id}", token=self.admin, payload={"name": "Release Control", "description": "Release train", "is_private": False})
        self.assertEqual(status, 200)
        status, data, _ = self.request("DELETE", f"/api/messages/{message_id}", token=self.moderator)
        self.assertEqual(status, 200)
        status, data, _ = self.request("DELETE", f"/api/channels/{release_id}", token=self.admin)
        self.assertEqual(status, 200)

    def test_channel_validation_and_forbidden_routes(self):
        status, data, _ = self.request(
            "POST",
            "/api/channels",
            token=self.alice,
            payload={"slug": "member-room", "name": "Member Room", "description": "Forbidden", "is_private": False},
        )
        self.assertEqual(status, 403)
        status, data, _ = self.request(
            "POST",
            "/api/channels",
            token=self.admin,
            payload={"slug": "x", "name": "N", "description": "D", "is_private": "no"},
        )
        self.assertEqual(status, 400)
        status, data, _ = self.request("PATCH", "/api/channels/999", token=self.admin, payload={"name": "Missing"})
        self.assertEqual(status, 404)
        status, data, _ = self.request("PATCH", "/api/channels/1", token=self.admin, payload={})
        self.assertEqual(status, 400)
        status, data, _ = self.request("POST", "/api/channels/1/members", token=self.admin, payload={"user_id": 1, "member_role": "captain"})
        self.assertEqual(status, 400)
        status, data, _ = self.request("GET", "/api/channels/abc", token=self.admin)
        self.assertEqual(status, 404)

    def test_message_ownership_and_not_found(self):
        status, data, _ = self.request("POST", "/api/channels/1/messages", token=self.alice, payload={"body": "Alice note"})
        self.assertEqual(status, 201)
        message_id = data["message"]["id"]
        status, data, _ = self.request(
            "POST",
            "/api/users",
            token=self.admin,
            payload={"email": "dave@corp.test", "name": "Dave", "password": "DavePass123", "role": "member"},
        )
        dave_token = self.login("dave@corp.test", "DavePass123")
        status, data, _ = self.request("DELETE", f"/api/messages/{message_id}", token=dave_token)
        self.assertEqual(status, 403)
        status, data, _ = self.request("PATCH", f"/api/messages/{message_id}", token=self.alice, payload={"body": ""})
        self.assertEqual(status, 400)
        status, data, _ = self.request("DELETE", "/api/messages/999", token=self.admin)
        self.assertEqual(status, 404)
        status, data, _ = self.request("GET", f"/api/messages/{message_id}", token=self.admin)
        self.assertEqual(status, 404)

    def test_integration_crud_validation_and_audit(self):
        status, data, _ = self.request("GET", "/api/integrations", token=self.admin)
        self.assertEqual(status, 200)
        before_count = len(data["integrations"])
        status, data, _ = self.request(
            "POST",
            "/api/integrations",
            token=self.admin,
            payload={"channel_id": 1, "name": "Calendar sync", "type": "calendar", "config": {"team": "ops"}, "enabled": True},
        )
        self.assertEqual(status, 201)
        integration_id = data["integration"]["id"]
        status, data, _ = self.request("PATCH", f"/api/integrations/{integration_id}", token=self.admin, payload={"name": "Security calendar", "enabled": False, "config": '{"team":"sec"}'})
        self.assertEqual(status, 200)
        self.assertFalse(data["integration"]["enabled"])
        status, data, _ = self.request("PATCH", f"/api/integrations/{integration_id}", token=self.admin, payload={})
        self.assertEqual(status, 200)
        status, data, _ = self.request("GET", "/api/integrations", token=self.admin)
        self.assertEqual(len(data["integrations"]), before_count + 1)
        status, data, _ = self.request("DELETE", f"/api/integrations/{integration_id}", token=self.admin)
        self.assertEqual(status, 200)
        status, data, _ = self.request("GET", "/api/integrations/bad", token=self.admin)
        self.assertEqual(status, 404)
        bad_payloads = [
            {"channel_id": 999, "name": "Missing channel", "type": "webhook", "config": {}, "enabled": True},
            {"channel_id": 1, "name": "Bad type", "type": "sms", "config": {}, "enabled": True},
            {"channel_id": 1, "name": "Bad config", "type": "webhook", "config": [1], "enabled": True},
            {"channel_id": 1, "name": "Bad enabled", "type": "webhook", "config": {}, "enabled": "yes"},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                status, data, _ = self.request("POST", "/api/integrations", token=self.admin, payload=payload)
                self.assertIn(status, (400, 404))
        status, data, _ = self.request("GET", "/api/integrations", token=self.alice)
        self.assertEqual(status, 403)
        status, data, _ = self.request("GET", "/api/audit-events", token=self.admin)
        self.assertEqual(status, 200)
        self.assertGreater(len(data["events"]), 0)
        status, data, _ = self.request("GET", "/api/audit-events/1", token=self.admin)
        self.assertEqual(status, 404)
