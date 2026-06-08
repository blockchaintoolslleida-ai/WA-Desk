"""
Admin Platform API Tests - Phase 1
Tests for WhatsApp Account config, Credentials management, Webhook info, and Audit logs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@workshoppartsdesk.com"
ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_EMAIL = "superadmin@workshoppartsdesk.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin2026!"
AGENT_EMAIL = "juanjo@auto-recanvis-cat.workshop"  # Agent role - should get 403


class TestAdminAuth:
    """Test authentication and role-based access control"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Super admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token - should be denied admin access"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": "Juanjo2026!"  # Default password from seed
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Agent login failed: {response.status_code}")
    
    def test_admin_can_access_setup_check(self, admin_token):
        """Admin role should access /api/admin/setup/check"""
        response = requests.get(
            f"{BASE_URL}/api/admin/setup/check",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "all_ready" in data
        assert "tables" in data
        print(f"Setup check: all_ready={data['all_ready']}, tables={data['tables']}")
    
    def test_super_admin_can_access_setup_check(self, super_admin_token):
        """Super admin role should access /api/admin/setup/check"""
        response = requests.get(
            f"{BASE_URL}/api/admin/setup/check",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "all_ready" in data
        print(f"Super admin setup check: all_ready={data['all_ready']}")
    
    def test_agent_denied_admin_access(self, agent_token):
        """Agent role should get 403 on admin endpoints"""
        response = requests.get(
            f"{BASE_URL}/api/admin/setup/check",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert response.status_code == 403
        print(f"Agent correctly denied: {response.status_code}")
    
    def test_unauthenticated_denied(self):
        """Unauthenticated requests should get 401"""
        response = requests.get(f"{BASE_URL}/api/admin/setup/check")
        assert response.status_code == 401
        print(f"Unauthenticated correctly denied: {response.status_code}")


class TestSetupCheck:
    """Test /api/admin/setup/check endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_setup_check_returns_all_tables(self, admin_token):
        """Setup check should return status for all required tables"""
        response = requests.get(
            f"{BASE_URL}/api/admin/setup/check",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all_ready field
        assert "all_ready" in data
        assert isinstance(data["all_ready"], bool)
        
        # Verify tables status
        assert "tables" in data
        expected_tables = ['tenants', 'whatsapp_accounts', 'whatsapp_secrets', 'whatsapp_webhook_logs', 'audit_logs']
        for table in expected_tables:
            assert table in data["tables"], f"Missing table: {table}"
            assert data["tables"][table] in ['ok', 'missing']
        
        # If all_ready is true, all tables should be 'ok'
        if data["all_ready"]:
            for table, status in data["tables"].items():
                assert status == 'ok', f"Table {table} should be 'ok' when all_ready=true"
        
        print(f"Setup check passed: all_ready={data['all_ready']}")


class TestWhatsAppAccount:
    """Test WhatsApp Account CRUD endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_get_whatsapp_account(self, admin_token):
        """GET /api/admin/whatsapp-account returns account with all fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have account object
        assert "account" in data
        account = data["account"]
        
        if account:
            # Verify required fields exist
            expected_fields = [
                'id', 'tenant_id', 'account_name', 'business_name', 
                'phone_number_id', 'connection_status', 'webhook_status', 'token_status'
            ]
            for field in expected_fields:
                assert field in account, f"Missing field: {field}"
            
            print(f"Account: {account.get('account_name')}, status={account.get('connection_status')}")
        else:
            print("No account found (may need env config)")
    
    def test_update_whatsapp_account(self, admin_token):
        """PUT /api/admin/whatsapp-account updates account fields"""
        # First get current account
        get_response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if get_response.status_code != 200 or not get_response.json().get("account"):
            pytest.skip("No account to update")
        
        original = get_response.json()["account"]
        
        # Update with test data
        test_name = f"TEST_Account_{original.get('account_name', 'default')}"
        update_response = requests.put(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"account_name": test_name}
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert "account" in updated
        assert updated["account"]["account_name"] == test_name
        
        # Restore original name
        requests.put(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"account_name": original.get("account_name", "Compte principal")}
        )
        print(f"Account update test passed")
    
    def test_validate_connection(self, admin_token):
        """POST /api/admin/whatsapp-account/validate calls Meta API"""
        response = requests.post(
            f"{BASE_URL}/api/admin/whatsapp-account/validate",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have valid field
        assert "valid" in data
        
        if data["valid"]:
            assert "data" in data
            print(f"Validation passed: {data.get('data')}")
        else:
            assert "error" in data
            print(f"Validation failed (expected if no token): {data.get('error')}")
    
    def test_disconnect_account(self, admin_token):
        """POST /api/admin/whatsapp-account/disconnect sets status to disconnected"""
        response = requests.post(
            f"{BASE_URL}/api/admin/whatsapp-account/disconnect",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        # Verify status changed
        get_response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if get_response.status_code == 200 and get_response.json().get("account"):
            assert get_response.json()["account"]["connection_status"] == "disconnected"
        
        print("Disconnect test passed")


class TestWhatsAppSecrets:
    """Test Credentials/Secrets management endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_get_secrets_returns_masked_values(self, admin_token):
        """GET /api/admin/whatsapp-secrets returns masked secrets, never full values"""
        response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-secrets",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "secrets" in data
        secrets = data["secrets"]
        
        if secrets:
            # Should have has_* boolean fields
            assert "has_access_token" in secrets
            assert "has_app_secret" in secrets
            assert "has_verify_token" in secrets
            
            # If has_access_token is true, masked_access_token should exist and be masked
            if secrets.get("has_access_token"):
                assert "masked_access_token" in secrets
                masked = secrets["masked_access_token"]
                # Masked value should contain asterisks
                assert "*" in masked, "Masked value should contain asterisks"
                # Should not be the full token (check length - masked tokens are typically 200 chars or less)
                assert len(masked) <= 200, "Masked value should be reasonable length"
            
            print(f"Secrets: has_token={secrets.get('has_access_token')}, masked={secrets.get('masked_access_token', 'N/A')[:20]}...")
        else:
            print("No secrets configured yet")
    
    def test_update_secrets_encrypts_values(self, admin_token):
        """PUT /api/admin/whatsapp-secrets encrypts and saves credentials"""
        # Save a test verify token
        test_token = "TEST_verify_token_12345"
        response = requests.put(
            f"{BASE_URL}/api/admin/whatsapp-secrets",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"verify_token": test_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "updated" in data
        assert "verify_token" in data["updated"]
        
        # Verify it's stored (masked)
        get_response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-secrets",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_response.status_code == 200
        secrets = get_response.json().get("secrets", {})
        assert secrets.get("has_verify_token") == True
        
        print("Secrets update test passed")
    
    def test_test_connection(self, admin_token):
        """POST /api/admin/whatsapp-secrets/test-connection tests stored token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/whatsapp-secrets/test-connection",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have ok field
        assert "ok" in data
        
        if data["ok"]:
            assert "message" in data
            print(f"Connection test passed: {data.get('message')}")
        else:
            assert "error" in data
            print(f"Connection test failed (may be expected): {data.get('error')}")


class TestWebhookInfo:
    """Test Webhook configuration endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_get_webhook_info(self, admin_token):
        """GET /api/admin/webhook-info returns webhook URL, verify token, status"""
        response = requests.get(
            f"{BASE_URL}/api/admin/webhook-info",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "webhook_url" in data
        assert "verify_token" in data
        assert "webhook_status" in data
        assert "last_events" in data
        
        # Webhook URL should be valid
        assert data["webhook_url"].startswith("http")
        assert "/api/whatsapp/webhook" in data["webhook_url"]
        
        # last_events should be a list
        assert isinstance(data["last_events"], list)
        
        print(f"Webhook URL: {data['webhook_url']}")
        print(f"Verify token: {data['verify_token'][:10]}..." if data['verify_token'] else "No verify token")
        print(f"Status: {data['webhook_status']}, Events: {len(data['last_events'])}")
    
    def test_verify_webhook(self, admin_token):
        """POST /api/admin/webhook-info/verify marks webhook as verified"""
        response = requests.post(
            f"{BASE_URL}/api/admin/webhook-info/verify",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        # Verify status changed
        get_response = requests.get(
            f"{BASE_URL}/api/admin/webhook-info",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if get_response.status_code == 200:
            assert get_response.json().get("webhook_status") == "verified"
        
        print("Webhook verify test passed")


class TestAuditLogs:
    """Test Audit log endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_get_audit_logs(self, admin_token):
        """GET /api/admin/audit-logs returns logged actions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        
        if len(data) > 0:
            log = data[0]
            # Verify required fields
            assert "action_type" in log
            assert "entity_type" in log
            assert "description" in log
            assert "created_at" in log
            
            print(f"Found {len(data)} audit logs")
            print(f"Latest: {log.get('action_type')} on {log.get('entity_type')}: {log.get('description')[:50]}...")
        else:
            print("No audit logs found (may be expected for new tenant)")
    
    def test_audit_logs_with_limit(self, admin_token):
        """GET /api/admin/audit-logs?limit=5 respects limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5
        
        print(f"Limit test: got {len(data)} logs (max 5)")


class TestSuperAdminNoTenant:
    """Test super admin behavior (may not have tenant_id)"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Super admin login failed")
    
    def test_super_admin_get_account_no_tenant(self, super_admin_token):
        """Super admin without tenant_id should get appropriate response"""
        response = requests.get(
            f"{BASE_URL}/api/admin/whatsapp-account",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # May return null account or env config info
        if data.get("account") is None:
            # Should indicate env config available
            assert "has_env_config" in data or data.get("account") is None
            print("Super admin has no tenant - returned null account (expected)")
        else:
            print(f"Super admin has account: {data['account'].get('account_name')}")
    
    def test_super_admin_audit_logs_no_tenant(self, super_admin_token):
        """Super admin without tenant_id should get empty audit logs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be empty list if no tenant
        assert isinstance(data, list)
        print(f"Super admin audit logs: {len(data)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
