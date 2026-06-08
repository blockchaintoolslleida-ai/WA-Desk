"""
Window 24h & Templates API Tests
Tests for WhatsApp 24h messaging window feature and template sending
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@workshoppartsdesk.com"
ADMIN_PASSWORD = "Admin123!"


class TestWindowAPI:
    """Tests for Window 24h status and template endpoints"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    @pytest.fixture(scope="class")
    def conversation_id(self, auth_headers):
        """Get a valid conversation ID for testing"""
        response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers)
        if response.status_code != 200 or not response.json():
            pytest.skip("No conversations available for testing")
        return response.json()[0]["id"]

    # ============ GET /api/window/status/{conversation_id} ============

    def test_window_status_returns_correct_fields(self, auth_headers, conversation_id):
        """Window status endpoint returns all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/window/status/{conversation_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all required fields are present
        assert "window_active" in data, "Missing window_active field"
        assert "window_expires_at" in data, "Missing window_expires_at field"
        assert "seconds_remaining" in data, "Missing seconds_remaining field"
        assert "hours_remaining" in data, "Missing hours_remaining field"
        assert "minutes_remaining" in data, "Missing minutes_remaining field"
        assert "last_customer_message_at" in data, "Missing last_customer_message_at field"
        
        # Verify types
        assert isinstance(data["window_active"], bool), "window_active should be boolean"
        assert isinstance(data["seconds_remaining"], int), "seconds_remaining should be int"
        assert isinstance(data["hours_remaining"], int), "hours_remaining should be int"
        assert isinstance(data["minutes_remaining"], int), "minutes_remaining should be int"
        
        print(f"Window status: active={data['window_active']}, hours_remaining={data['hours_remaining']}")

    def test_window_status_unauthenticated_rejected(self, conversation_id):
        """Window status endpoint rejects unauthenticated requests"""
        response = requests.get(f"{BASE_URL}/api/window/status/{conversation_id}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_window_status_invalid_conversation(self, auth_headers):
        """Window status for non-existent conversation returns valid response (no incoming messages)"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/window/status/{fake_id}",
            headers=auth_headers
        )
        # Should return 200 with window_active=False (no incoming messages)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["window_active"] == False, "Window should be inactive for non-existent conversation"
        assert data["seconds_remaining"] == 0, "Seconds remaining should be 0"

    # ============ GET /api/templates ============

    def test_templates_list_returns_templates(self, auth_headers):
        """Templates endpoint returns list of available templates"""
        response = requests.get(f"{BASE_URL}/api/templates", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Templates should be a list"
        assert len(templates) > 0, "Should have at least one template"
        
        # Verify template structure
        template = templates[0]
        assert "id" in template, "Template missing id"
        assert "name" in template, "Template missing name"
        assert "languages" in template, "Template missing languages"
        assert "variables" in template, "Template missing variables"
        
        # Verify languages
        assert isinstance(template["languages"], dict), "Languages should be a dict"
        assert "ca" in template["languages"] or "es" in template["languages"] or "en" in template["languages"], \
            "Template should have at least one language"
        
        print(f"Found {len(templates)} templates: {[t['id'] for t in templates]}")

    def test_templates_list_unauthenticated_rejected(self):
        """Templates endpoint rejects unauthenticated requests"""
        response = requests.get(f"{BASE_URL}/api/templates")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    # ============ POST /api/templates/send/{conversation_id} ============

    def test_template_send_success(self, auth_headers, conversation_id):
        """Sending a template message succeeds and saves message"""
        # First get templates to use a valid template_id
        templates_response = requests.get(f"{BASE_URL}/api/templates", headers=auth_headers)
        templates = templates_response.json()
        template_id = templates[0]["id"]
        
        # Send template
        response = requests.post(
            f"{BASE_URL}/api/templates/send/{conversation_id}",
            headers=auth_headers,
            json={
                "template_id": template_id,
                "language": "ca",
                "variables": {"customer_name": "Test Customer"}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain message id"
        assert "body" in data, "Response should contain body"
        assert "template_used" in data, "Response should contain template_used"
        assert "whatsapp_sent" in data, "Response should contain whatsapp_sent status"
        
        # Verify the message was saved by checking conversation messages
        messages_response = requests.get(
            f"{BASE_URL}/api/conversations/{conversation_id}/messages",
            headers=auth_headers
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()
        
        # Find our template message
        template_msg = next((m for m in messages if m["id"] == data["id"]), None)
        assert template_msg is not None, "Template message should be saved in messages table"
        assert "[Plantilla]" in template_msg["body"], "Message body should contain [Plantilla] prefix"
        
        print(f"Template sent: id={data['id']}, whatsapp_sent={data['whatsapp_sent']}")

    def test_template_send_invalid_template(self, auth_headers, conversation_id):
        """Sending with invalid template_id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/templates/send/{conversation_id}",
            headers=auth_headers,
            json={
                "template_id": "nonexistent_template",
                "language": "ca",
                "variables": {}
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_template_send_invalid_conversation(self, auth_headers):
        """Sending to non-existent conversation returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/templates/send/{fake_id}",
            headers=auth_headers,
            json={
                "template_id": "followup_generic",
                "language": "ca",
                "variables": {}
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_template_send_unauthenticated_rejected(self, conversation_id):
        """Template send endpoint rejects unauthenticated requests"""
        response = requests.post(
            f"{BASE_URL}/api/templates/send/{conversation_id}",
            json={"template_id": "followup_generic", "language": "ca", "variables": {}}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    # ============ GET /api/conversations (with window data) ============

    def test_conversations_list_includes_window_data(self, auth_headers):
        """Conversation list includes window object with window_active and seconds_remaining"""
        response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        conversations = response.json()
        assert len(conversations) > 0, "Should have at least one conversation"
        
        # Check first conversation has window data
        conv = conversations[0]
        assert "window" in conv, "Conversation should have window object"
        
        window = conv["window"]
        assert "window_active" in window, "Window should have window_active"
        assert "seconds_remaining" in window, "Window should have seconds_remaining"
        assert "hours_remaining" in window, "Window should have hours_remaining"
        assert "minutes_remaining" in window, "Window should have minutes_remaining"
        
        # Count active vs expired windows
        active_count = sum(1 for c in conversations if c.get("window", {}).get("window_active", False))
        expired_count = len(conversations) - active_count
        print(f"Conversations: {len(conversations)} total, {active_count} active windows, {expired_count} expired")

    # ============ GET /api/conversations/{id} (with window data) ============

    def test_conversation_detail_includes_window_data(self, auth_headers, conversation_id):
        """Conversation detail includes window object with full status"""
        response = requests.get(
            f"{BASE_URL}/api/conversations/{conversation_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        conv = response.json()
        assert "window" in conv, "Conversation detail should have window object"
        
        window = conv["window"]
        assert "window_active" in window, "Window should have window_active"
        assert "window_expires_at" in window, "Window should have window_expires_at"
        assert "seconds_remaining" in window, "Window should have seconds_remaining"
        assert "hours_remaining" in window, "Window should have hours_remaining"
        assert "minutes_remaining" in window, "Window should have minutes_remaining"
        assert "last_customer_message_at" in window, "Window should have last_customer_message_at"
        
        print(f"Conversation {conversation_id} window: active={window['window_active']}, "
              f"hours_remaining={window['hours_remaining']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
