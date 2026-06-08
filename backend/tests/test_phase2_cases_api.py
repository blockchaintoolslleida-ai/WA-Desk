"""
Phase 2 Cases API Tests - Multi-case architecture, cases CRUD, message classification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    def test_login_admin(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        print(f"Login successful: {data['user'].get('email')}")
        return data["access_token"]


class TestConversations:
    """Conversation list and detail tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        return response.json()["access_token"]
    
    def test_list_conversations(self, auth_token):
        """Test listing conversations with case enrichment"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 4, f"Expected at least 4 conversations, got {len(data)}"
        
        # Check enrichment fields
        for conv in data:
            assert "contact" in conv, "Missing contact field"
            assert "cases_count" in conv, "Missing cases_count field"
            assert "pending_cases" in conv, "Missing pending_cases field"
            assert "unclassified_count" in conv, "Missing unclassified_count field"
            assert "derived_status" in conv, "Missing derived_status field"
        
        print(f"Found {len(data)} conversations with case enrichment")
        return data
    
    def test_filter_with_pending(self, auth_token):
        """Test filter for conversations with pending cases"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/conversations?filter=with_pending", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"With pending filter: {len(data)} conversations")
    
    def test_filter_in_progress(self, auth_token):
        """Test filter for conversations in progress"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/conversations?filter=in_progress", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"In progress filter: {len(data)} conversations")
    
    def test_get_conversation_detail(self, auth_token):
        """Test getting conversation detail with cases"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # First get list to find a conversation ID
        list_response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        conversations = list_response.json()
        
        # Find Maria Lopez (should have 2 cases)
        maria_conv = None
        for conv in conversations:
            if conv.get("contact", {}).get("name") == "Maria Lopez":
                maria_conv = conv
                break
        
        assert maria_conv is not None, "Maria Lopez conversation not found"
        
        # Get detail
        response = requests.get(f"{BASE_URL}/api/conversations/{maria_conv['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "cases" in data, "Missing cases in detail"
        assert len(data["cases"]) == 2, f"Expected 2 cases for Maria Lopez, got {len(data['cases'])}"
        assert "unclassified_count" in data, "Missing unclassified_count"
        
        print(f"Maria Lopez has {len(data['cases'])} cases, {data['unclassified_count']} unclassified messages")
        return data
    
    def test_get_conversation_messages(self, auth_token):
        """Test getting messages for a conversation"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        list_response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        conversations = list_response.json()
        
        if conversations:
            conv_id = conversations[0]["id"]
            response = requests.get(f"{BASE_URL}/api/conversations/{conv_id}/messages", headers=headers)
            assert response.status_code == 200
            messages = response.json()
            assert isinstance(messages, list)
            print(f"Conversation has {len(messages)} messages")


class TestCases:
    """Cases CRUD tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def conversation_id(self, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        conversations = response.json()
        # Find Pere Martinez (has no cases)
        for conv in conversations:
            if conv.get("contact", {}).get("name") == "Pere Martinez":
                return conv["id"]
        return conversations[0]["id"] if conversations else None
    
    def test_list_all_cases(self, auth_token):
        """Test listing all cases"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        assert response.status_code == 200
        cases = response.json()
        assert isinstance(cases, list)
        assert len(cases) >= 4, f"Expected at least 4 cases, got {len(cases)}"
        
        # Check case fields
        for case in cases:
            assert "id" in case
            assert "title" in case
            assert "status" in case
            assert "is_active" in case
        
        print(f"Found {len(cases)} total cases")
        return cases
    
    def test_create_case(self, auth_token, conversation_id):
        """Test creating a new case"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        case_data = {
            "conversation_id": conversation_id,
            "title": "TEST_Case_Creation_Test",
            "description": "Test case created by automated test",
            "priority": "high",
            "initial_note": "Initial test note"
        }
        response = requests.post(f"{BASE_URL}/api/cases", json=case_data, headers=headers)
        assert response.status_code == 200, f"Create case failed: {response.text}"
        
        created_case = response.json()
        assert created_case["title"] == case_data["title"]
        assert created_case["status"] == "per_atendre"  # Default status
        assert created_case["priority"] == "high"
        assert created_case["is_active"] == True
        
        print(f"Created case: {created_case['id']}")
        return created_case
    
    def test_get_case_detail(self, auth_token):
        """Test getting case detail"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get a case first
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        if cases:
            case_id = cases[0]["id"]
            response = requests.get(f"{BASE_URL}/api/cases/{case_id}", headers=headers)
            assert response.status_code == 200
            case = response.json()
            assert "id" in case
            assert "title" in case
            assert "message_count" in case
            print(f"Case detail: {case['title']}, {case['message_count']} messages")
    
    def test_change_case_status(self, auth_token):
        """Test changing case status"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get a case first
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        # Find an active case
        active_case = None
        for case in cases:
            if case.get("is_active") and case.get("status") != "resolt":
                active_case = case
                break
        
        if active_case:
            case_id = active_case["id"]
            original_status = active_case["status"]
            
            # Change to en_atencio
            response = requests.patch(
                f"{BASE_URL}/api/cases/{case_id}/status",
                json={"status": "en_atencio"},
                headers=headers
            )
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "en_atencio"
            print(f"Changed status from {original_status} to en_atencio")
            
            # Change back
            requests.patch(
                f"{BASE_URL}/api/cases/{case_id}/status",
                json={"status": original_status},
                headers=headers
            )
    
    def test_assign_case(self, auth_token):
        """Test assigning a case"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        if cases:
            case_id = cases[0]["id"]
            # Assign to self (agent_id=None means assign to current user)
            response = requests.post(
                f"{BASE_URL}/api/cases/{case_id}/assign",
                json={"agent_id": None},
                headers=headers
            )
            assert response.status_code == 200
            result = response.json()
            assert "assigned_agent_id" in result
            print(f"Assigned case to: {result.get('agent_name')}")
    
    def test_case_notes(self, auth_token):
        """Test case notes CRUD"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        if cases:
            case_id = cases[0]["id"]
            
            # Create note
            response = requests.post(
                f"{BASE_URL}/api/cases/{case_id}/notes",
                json={"note": "TEST_Note from automated test"},
                headers=headers
            )
            assert response.status_code == 200
            note = response.json()
            assert "id" in note
            assert note["note"] == "TEST_Note from automated test"
            print(f"Created note: {note['id']}")
            
            # List notes
            list_response = requests.get(f"{BASE_URL}/api/cases/{case_id}/notes", headers=headers)
            assert list_response.status_code == 200
            notes = list_response.json()
            assert isinstance(notes, list)
            print(f"Case has {len(notes)} notes")
    
    def test_case_events(self, auth_token):
        """Test case events (audit trail)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        if cases:
            case_id = cases[0]["id"]
            response = requests.get(f"{BASE_URL}/api/cases/{case_id}/events", headers=headers)
            assert response.status_code == 200
            events = response.json()
            assert isinstance(events, list)
            
            # Check event structure
            if events:
                event = events[0]
                assert "event_type" in event
                assert "created_at" in event
            
            print(f"Case has {len(events)} events")
    
    def test_link_messages_to_case(self, auth_token):
        """Test linking messages to a case"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Get conversations to find one with unclassified messages
        conv_response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        conversations = conv_response.json()
        
        # Find Pere Martinez (has unclassified messages)
        pere_conv = None
        for conv in conversations:
            if conv.get("contact", {}).get("name") == "Pere Martinez":
                pere_conv = conv
                break
        
        if pere_conv and pere_conv.get("unclassified_count", 0) > 0:
            # Get messages
            msg_response = requests.get(
                f"{BASE_URL}/api/conversations/{pere_conv['id']}/messages",
                headers=headers
            )
            messages = msg_response.json()
            
            # Find unclassified messages
            unclassified = [m for m in messages if m.get("needs_classification") or not m.get("case_id")]
            
            if unclassified:
                # Create a case and link messages
                case_data = {
                    "conversation_id": pere_conv["id"],
                    "title": "TEST_Link_Messages_Test",
                    "message_ids": [unclassified[0]["id"]]
                }
                response = requests.post(f"{BASE_URL}/api/cases", json=case_data, headers=headers)
                assert response.status_code == 200
                print(f"Created case with linked message")


class TestDashboard:
    """Dashboard metrics tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        return response.json()["access_token"]
    
    def test_get_metrics(self, auth_token):
        """Test dashboard metrics"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics", headers=headers)
        assert response.status_code == 200
        
        metrics = response.json()
        
        # Check required fields
        required_fields = [
            "new_today", "per_atendre", "en_atencio", "esperant_client",
            "closed_today", "unassigned", "total_active", "total_cases",
            "unclassified_msgs", "multi_case_convs", "cases_by_agent", "resolved_by_agent"
        ]
        
        for field in required_fields:
            assert field in metrics, f"Missing field: {field}"
        
        print(f"Dashboard metrics: {metrics['total_cases']} total cases, {metrics['total_active']} active")
        print(f"Per atendre: {metrics['per_atendre']}, En atenció: {metrics['en_atencio']}")
        print(f"Unclassified messages: {metrics['unclassified_msgs']}")


class TestAgents:
    """Agents list tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        return response.json()["access_token"]
    
    def test_list_agents(self, auth_token):
        """Test listing agents"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agents", headers=headers)
        assert response.status_code == 200
        
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) >= 2, f"Expected at least 2 agents, got {len(agents)}"
        
        # Check agent fields
        for agent in agents:
            assert "id" in agent
            assert "full_name" in agent
            assert "role" in agent
        
        print(f"Found {len(agents)} agents")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@workshoppartsdesk.com",
            "password": "Admin123!"
        })
        return response.json()["access_token"]
    
    def test_cleanup_test_cases(self, auth_token):
        """Clean up TEST_ prefixed cases"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        cases_response = requests.get(f"{BASE_URL}/api/cases", headers=headers)
        cases = cases_response.json()
        
        test_cases = [c for c in cases if c.get("title", "").startswith("TEST_")]
        print(f"Found {len(test_cases)} test cases to clean up")
        
        # Note: No delete endpoint, so we just mark them as closed
        for case in test_cases:
            requests.patch(
                f"{BASE_URL}/api/cases/{case['id']}/status",
                json={"status": "tancat"},
                headers=headers
            )
        
        print("Test cases marked as closed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
