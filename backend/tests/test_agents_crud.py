"""
Test Agents CRUD API - Create, Update, Delete operations
Tests role hierarchy: super_admin > admin > agent
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@workshoppartsdesk.com"
ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_EMAIL = "superadmin@workshoppartsdesk.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin2026!"


class TestAgentsCRUD:
    """Agents CRUD endpoint tests with role hierarchy"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in login response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super_admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in login response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def super_admin_headers(self, super_admin_token):
        """Headers with super_admin auth"""
        return {"Authorization": f"Bearer {super_admin_token}", "Content-Type": "application/json"}
    
    # ============ LIST AGENTS ============
    def test_list_agents_authenticated(self, admin_headers):
        """GET /api/agents - List all agents (authenticated)"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=admin_headers)
        assert response.status_code == 200, f"List agents failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Verify structure of agent objects
        if len(data) > 0:
            agent = data[0]
            assert "id" in agent
            assert "full_name" in agent
            assert "email" in agent
            assert "role" in agent
            assert "is_active" in agent
        print(f"✓ Listed {len(data)} agents")
    
    def test_list_agents_unauthenticated(self):
        """GET /api/agents - Should fail without auth"""
        response = requests.get(f"{BASE_URL}/api/agents")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected")
    
    # ============ CREATE AGENT (Admin) ============
    def test_admin_create_agent_role(self, admin_headers):
        """POST /api/agents - Admin can create agent role"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"test_agent_{unique_id}@test.com"
        
        payload = {
            "full_name": f"Test Agent {unique_id}",
            "email": test_email,
            "password": "TestPass123!",
            "role": "agent",
            "phone": "+34600000001"
        }
        
        response = requests.post(f"{BASE_URL}/api/agents", json=payload, headers=admin_headers)
        assert response.status_code == 200, f"Create agent failed: {response.text}"
        
        data = response.json()
        assert data["full_name"] == payload["full_name"]
        assert data["email"] == test_email
        assert data["role"] == "agent"
        assert data["is_active"] == True
        
        # Store agent ID for cleanup
        self.__class__.created_agent_id = data["id"]
        self.__class__.created_agent_email = test_email
        print(f"✓ Admin created agent: {test_email}")
        return data["id"]
    
    def test_admin_cannot_create_admin_role(self, admin_headers):
        """POST /api/agents - Admin cannot create admin role (only super_admin can)"""
        unique_id = str(uuid.uuid4())[:8]
        
        payload = {
            "full_name": f"Test Admin {unique_id}",
            "email": f"test_admin_{unique_id}@test.com",
            "password": "TestPass123!",
            "role": "admin"  # Trying to create admin role
        }
        
        response = requests.post(f"{BASE_URL}/api/agents", json=payload, headers=admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Admin correctly blocked from creating admin role")
    
    # ============ VERIFY CREATED AGENT ============
    def test_verify_created_agent_in_list(self, admin_headers):
        """GET /api/agents - Verify created agent appears in list"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=admin_headers)
        assert response.status_code == 200
        
        agents = response.json()
        created_agent = next((a for a in agents if a.get("id") == self.__class__.created_agent_id), None)
        
        assert created_agent is not None, f"Created agent not found in list"
        assert created_agent["email"] == self.__class__.created_agent_email
        assert created_agent["is_active"] == True
        print(f"✓ Created agent verified in list")
    
    # ============ UPDATE AGENT ============
    def test_admin_update_agent(self, admin_headers):
        """PUT /api/agents/{id} - Admin can update agent"""
        agent_id = self.__class__.created_agent_id
        
        update_payload = {
            "full_name": "Updated Agent Name",
            "phone": "+34600000002"
        }
        
        response = requests.put(f"{BASE_URL}/api/agents/{agent_id}", json=update_payload, headers=admin_headers)
        assert response.status_code == 200, f"Update agent failed: {response.text}"
        
        data = response.json()
        assert data.get("full_name") == "Updated Agent Name" or data.get("ok") == True
        print(f"✓ Admin updated agent successfully")
    
    def test_verify_agent_update_persisted(self, admin_headers):
        """GET /api/agents - Verify update was persisted"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=admin_headers)
        assert response.status_code == 200
        
        agents = response.json()
        updated_agent = next((a for a in agents if a.get("id") == self.__class__.created_agent_id), None)
        
        assert updated_agent is not None
        assert updated_agent["full_name"] == "Updated Agent Name"
        assert updated_agent["phone"] == "+34600000002"
        print(f"✓ Agent update verified in database")
    
    # ============ DELETE (DEACTIVATE) AGENT ============
    def test_admin_delete_agent(self, admin_headers):
        """DELETE /api/agents/{id} - Admin can deactivate agent"""
        agent_id = self.__class__.created_agent_id
        
        response = requests.delete(f"{BASE_URL}/api/agents/{agent_id}", headers=admin_headers)
        assert response.status_code == 200, f"Delete agent failed: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("deactivated") == True
        print(f"✓ Admin deactivated agent successfully")
    
    def test_verify_agent_deactivated(self, admin_headers):
        """GET /api/agents - Verify agent is_active is now false"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=admin_headers)
        assert response.status_code == 200
        
        agents = response.json()
        deactivated_agent = next((a for a in agents if a.get("id") == self.__class__.created_agent_id), None)
        
        assert deactivated_agent is not None, "Agent should still exist (soft delete)"
        assert deactivated_agent["is_active"] == False, "Agent should be deactivated"
        print(f"✓ Agent deactivation verified (is_active=False)")


class TestSuperAdminAgentsCRUD:
    """Super Admin specific CRUD tests"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super_admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        data = response.json()
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def super_admin_headers(self, super_admin_token):
        """Headers with super_admin auth"""
        return {"Authorization": f"Bearer {super_admin_token}", "Content-Type": "application/json"}
    
    def test_super_admin_can_create_admin_role(self, super_admin_headers):
        """POST /api/agents - Super admin CAN create admin role"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"test_admin_{unique_id}@test.com"
        
        payload = {
            "full_name": f"Test Admin {unique_id}",
            "email": test_email,
            "password": "TestPass123!",
            "role": "admin"  # Super admin can create admin role
        }
        
        response = requests.post(f"{BASE_URL}/api/agents", json=payload, headers=super_admin_headers)
        assert response.status_code == 200, f"Super admin create admin failed: {response.text}"
        
        data = response.json()
        assert data["role"] == "admin"
        
        # Store for cleanup
        self.__class__.created_admin_id = data["id"]
        print(f"✓ Super admin created admin role: {test_email}")
    
    def test_super_admin_delete_created_admin(self, super_admin_headers):
        """DELETE /api/agents/{id} - Cleanup: deactivate created admin"""
        if hasattr(self.__class__, 'created_admin_id'):
            agent_id = self.__class__.created_admin_id
            response = requests.delete(f"{BASE_URL}/api/agents/{agent_id}", headers=super_admin_headers)
            assert response.status_code == 200, f"Cleanup delete failed: {response.text}"
            print(f"✓ Cleaned up test admin")


class TestAgentsDuplicateEmail:
    """Test duplicate email handling"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    def test_duplicate_email_rejected(self, admin_headers):
        """POST /api/agents - Duplicate email should be rejected"""
        # Try to create agent with existing admin email
        payload = {
            "full_name": "Duplicate Test",
            "email": ADMIN_EMAIL,  # Already exists
            "password": "TestPass123!",
            "role": "agent"
        }
        
        response = requests.post(f"{BASE_URL}/api/agents", json=payload, headers=admin_headers)
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
        print("✓ Duplicate email correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
