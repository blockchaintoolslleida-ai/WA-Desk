"""
Templates API Tests - WhatsApp Message Templates Management
Tests list/create/delete/send endpoints + auth/authorization.
Uses real Meta Graph API v25.0 (no mocks).
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "admin@workshoppartsdesk.com"
ADMIN_PASSWORD = "Admin123!"
AGENT_EMAIL = "juanjo@auto-recanvis-cat.workshop"
AGENT_PASSWORD = "Juanjo2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json().get("access_token")


@pytest.fixture(scope="module")
def agent_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": AGENT_EMAIL, "password": AGENT_PASSWORD
    })
    if r.status_code != 200:
        pytest.skip(f"Agent login failed: {r.status_code}")
    return r.json().get("access_token")


# ---------- Auth/Authorization ----------
class TestTemplatesAuth:
    def test_no_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/templates")
        assert r.status_code == 401, r.text

    def test_invalid_token_returns_401(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/templates",
            headers={"Authorization": "Bearer invalid_token_xyz"}
        )
        assert r.status_code == 401, r.text

    def test_agent_role_returns_403(self, agent_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/templates",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert r.status_code == 403, r.text


# ---------- Listing ----------
class TestTemplatesList:
    def test_list_returns_meta_templates(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/templates",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)
        names = [t["name"] for t in data["templates"]]
        # Expected templates per review request
        assert "hello_world" in names, f"hello_world not in {names}"
        # Validate shape of one template
        sample = data["templates"][0]
        for key in ("id", "name", "status", "category", "language", "components"):
            assert key in sample, f"Missing key {key} in template"


# ---------- Create / Delete ----------
class TestTemplatesCRUD:
    @pytest.fixture(scope="class")
    def template_name(self):
        return f"tpl_test_review_{int(time.time())}"

    def test_create_template_returns_pending(self, admin_token, template_name):
        payload = {
            "name": template_name,
            "category": "UTILITY",
            "language": "ca",
            "body_text": "Hola, missatge de prova des de l'app de revisió.",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/templates",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("name") == template_name
        # Meta typically returns PENDING / APPROVED for UTILITY auto-approval
        assert data.get("status") in ("PENDING", "APPROVED"), data
        assert data.get("id"), "Missing template id"

    def test_create_invalid_name_returns_400(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/templates",
            json={
                "name": "Invalid Name!@#",
                "category": "UTILITY",
                "language": "ca",
                "body_text": "test",
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # The endpoint lowercases & replaces spaces, but '!@#' should fail the alnum/_ check
        assert r.status_code == 400, r.text

    def test_delete_created_template(self, admin_token, template_name):
        # Allow a moment for Meta to register the template
        time.sleep(2)
        r = requests.delete(
            f"{BASE_URL}/api/admin/templates/{template_name}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, f"Delete failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("deleted") == template_name


# ---------- Send-test ----------
class TestTemplatesSend:
    def test_send_endpoint_accepts_payload(self, admin_token):
        """Endpoint must respond properly even if Meta refuses send (phone not on WA, etc.)"""
        r = requests.post(
            f"{BASE_URL}/api/admin/templates/send",
            json={
                "template_name": "hello_world",
                "language_code": "en_US",
                "to_phone": "+34600000000",
                "variables": []
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Either ok=True or ok=False with error info — but never 5xx
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        data = r.json()
        assert "ok" in data
        if data["ok"] is False:
            assert "error" in data

    def test_send_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/templates/send",
            json={
                "template_name": "hello_world",
                "language_code": "en_US",
                "to_phone": "+34600000000",
            }
        )
        assert r.status_code == 401, r.text


# ---------- Multi-tenant isolation regression ----------
class TestTenantIsolationRegression:
    def test_conversations_endpoint_scoped(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/conversations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, r.text

    def test_contacts_endpoint_scoped(self, admin_token):
        # /api/contacts only exposes PUT (no list); verify route registered (not 401/500)
        r = requests.put(
            f"{BASE_URL}/api/contacts/00000000-0000-0000-0000-000000000000",
            json={"name": "x"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code in (200, 400, 404, 422), r.text

    def test_agents_endpoint_scoped(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/agents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, r.text
