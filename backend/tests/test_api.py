import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Task, User
from app.schemas import AssigneeEnum, CategoryEnum, PriorityEnum

client = TestClient(app)

def test_get_users(db):
    """
    Checks that GET /users returns the correct seeded team roster list.
    """
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    
    user_ids = [u["user_id"] for u in data]
    assert "u_aarti" in user_ids
    assert "u_triage" in user_ids

def test_invalid_enum_validation(db):
    """
    Checks that submitting an invalid enum returns the required custom HTTP 400 response structure.
    """
    invalid_payload = {
        "candidate_id": "kanhaiyak0104@gmail.com",
        "source_email_id": "em_test_api_01",
        "thread_id": "th_test_api_01",
        "title": "Invalid task",
        "assignee_id": "Aarti",  # Invalid enum value! Should be u_aarti
        "category": "enterprise_rfp",
        "priority": "medium",
        "confidence": 0.9
    }
    
    response = client.post("/tasks", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "invalid_enum_value"
    assert data["field"] == "assignee_id"
    assert data["received"] == "Aarti"
    assert "u_aarti" in data["allowed"]

def test_task_crud_lifecycle(db):
    """
    Verifies full lifecycle of task management: POST, GET, PATCH, and DELETE.
    """
    # Create task
    task_payload = {
        "candidate_id": "kanhaiyak0104@gmail.com",
        "source_email_id": "em_crud_01",
        "thread_id": "th_crud_01",
        "title": "CRM Implementation RFP",
        "assignee_id": "u_aarti",
        "category": "enterprise_rfp",
        "priority": "high",
        "due_date": "2026-09-01",
        "deal_value_inr": 2000000,
        "company_name": "Acme Corp",
        "confidence": 0.95
    }
    
    post_res = client.post("/tasks", json=task_payload)
    assert post_res.status_code == 201
    post_data = post_res.json()
    task_id = post_data["task_id"]
    
    # Get task with filtering
    get_res = client.get(f"/tasks?candidate_id=kanhaiyak0104@gmail.com&thread_id=th_crud_01")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert len(get_data) == 1
    assert get_data[0]["title"] == "CRM Implementation RFP"

    # Patch task
    patch_payload = {
        "priority": "medium",
        "deal_value_inr": 2200000
    }
    patch_res = client.patch(f"/tasks/{task_id}", json=patch_payload)
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["priority"] == "medium"
    assert patch_data["deal_value_inr"] == 2200000

    # Delete task
    del_res = client.delete(f"/tasks/{task_id}")
    assert del_res.status_code == 200
    
    # Confirm deletion
    get_confirm = client.get(f"/tasks?candidate_id=kanhaiyak0104@gmail.com&thread_id=th_crud_01")
    assert len(get_confirm.json()) == 0
