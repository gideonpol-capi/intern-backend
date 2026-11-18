"""Task 2: serializers, viewsets, routers and the API schema."""
import datetime

import pytest

from .conftest import get_model, ids, results

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def client(as_user, alice):
    return as_user(alice)


def test_create_and_read_a_list(client, alice):
    response = client.post("/api/lists/", {"title": "Groceries"}, format="json")
    assert response.status_code == 201, response.content
    list_id = response.json()["id"]
    assert get_model("todos", "TodoList").objects.get(id=list_id).owner == alice, (
        "The owner of a new list is the user making the request (set it in perform_create)."
    )
    assert list_id in ids(results(client.get("/api/lists/")))
    detail = client.get(f"/api/lists/{list_id}/")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Groceries"


def test_owner_cannot_be_set_by_the_client(client, make_user, alice):
    mallory = make_user("mallory")
    response = client.post("/api/lists/", {"title": "Mine", "owner": mallory.id}, format="json")
    assert response.status_code == 201
    created = get_model("todos", "TodoList").objects.get(id=response.json()["id"])
    assert created.owner == alice, "owner must be read-only: the client must not be able to choose it."


def test_update_and_delete_a_list(client, alice, make_list):
    todo_list = make_list(alice)
    response = client.patch(f"/api/lists/{todo_list.id}/", {"title": "Shopping"}, format="json")
    assert response.status_code == 200
    assert response.json()["title"] == "Shopping"
    assert client.delete(f"/api/lists/{todo_list.id}/").status_code == 204
    assert client.get(f"/api/lists/{todo_list.id}/").status_code == 404


def test_create_item_with_tags(client, alice, make_list):
    todo_list = make_list(alice)
    tag = client.post("/api/tags/", {"name": "dairy"}, format="json")
    assert tag.status_code == 201, tag.content
    response = client.post(
        "/api/items/",
        {"todo_list": str(todo_list.id), "title": "Milk", "priority": "high", "tags": [tag.json()["id"]]},
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    for key in ("id", "todo_list", "title", "description", "is_completed", "completed_at",
                "priority", "due_date", "assigned_to", "tags", "created_at", "updated_at"):
        assert key in body, f"The item response is missing '{key}'."
    item = get_model("todos", "TodoItem").objects.get(id=body["id"])
    assert list(item.tags.values_list("name", flat=True)) == ["dairy"]


def test_completed_at_is_read_only(client, alice, make_list, make_item):
    item = make_item(make_list(alice))
    client.patch(f"/api/items/{item.id}/", {"completed_at": "2020-01-01T00:00:00Z"}, format="json")
    item.refresh_from_db()
    assert item.completed_at is None, "completed_at is set by the complete action, not by the client."


def test_complete_action_is_idempotent(client, alice, make_list, make_item):
    item = make_item(make_list(alice))
    first = client.post(f"/api/items/{item.id}/complete/")
    assert first.status_code == 200, "Add a POST /api/items/<id>/complete/ action (@action(detail=True))."
    assert first.json()["is_completed"] is True
    item.refresh_from_db()
    completed_at = item.completed_at
    assert completed_at is not None
    second = client.post(f"/api/items/{item.id}/complete/")
    assert second.status_code == 200, "Completing an item twice is not an error."
    item.refresh_from_db()
    assert item.completed_at == completed_at, "Completing an item twice must not move completed_at."


def test_title_must_not_be_blank(client, alice, make_list):
    response = client.post("/api/lists/", {"title": "   "}, format="json")
    assert response.status_code == 400
    assert "title" in response.json(), "Return the error under the 'title' key."
    todo_list = make_list(alice)
    response = client.post("/api/items/", {"todo_list": str(todo_list.id), "title": "  "}, format="json")
    assert response.status_code == 400
    assert "title" in response.json()


def test_due_date_cannot_be_in_the_past(client, alice, make_list):
    todo_list = make_list(alice)
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    response = client.post("/api/items/", {"todo_list": str(todo_list.id), "title": "Milk", "due_date": yesterday}, format="json")
    assert response.status_code == 400
    assert "due_date" in response.json(), "Validate due_date in the serializer (validate_due_date)."


def test_anonymous_requests_are_rejected(api):
    assert api.get("/api/lists/").status_code in (401, 403)


def test_schema_and_docs(api):
    assert api.get("/api/schema/").status_code == 200, "Expose the OpenAPI schema at /api/schema/ (drf-spectacular)."
    assert api.get("/api/docs/").status_code == 200, "Expose Swagger UI at /api/docs/."
