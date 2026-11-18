"""Task 5: no N+1 queries, and expandable fields with drf-flex-fields."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .conftest import get_model

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(make_user):
    return make_user("alice")


def build(owner, make_user, make_list, make_item, n_lists, n_items):
    tags = [get_model("todos", "Tag").objects.get_or_create(name=f"tag{n}")[0] for n in range(3)]
    helper = make_user(f"helper{n_lists}")
    for l in range(n_lists):
        todo_list = make_list(owner, f"List {l}")
        for i in range(n_items):
            item = make_item(todo_list, f"Item {i}", assigned_to=helper if i % 2 else None, is_completed=i % 3 == 0)
            item.tags.set(tags[: i % 3 + 1])


def count_queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200, response.content
    return len(ctx.captured_queries), response.json()


def test_lists_endpoint_has_counts(as_user, alice, make_list, make_item):
    todo_list = make_list(alice)
    make_item(todo_list, "a", is_completed=True)
    make_item(todo_list, "b")
    row = as_user(alice).get("/api/lists/").json()["results"][0]
    assert row["item_count"] == 2, "Add item_count to the list serializer (use annotate, not len())."
    assert row["completed_count"] == 1, "Add completed_count to the list serializer."


@pytest.mark.parametrize("url", ["/api/lists/", "/api/items/", "/api/items/?expand=assigned_to,tags,todo_list"])
def test_query_count_does_not_grow_with_the_data(as_user, alice, make_user, make_list, make_item, url):
    client = as_user(alice)
    build(alice, make_user, make_list, make_item, n_lists=2, n_items=2)
    small, _ = count_queries(client, url)
    build(alice, make_user, make_list, make_item, n_lists=8, n_items=4)
    large, _ = count_queries(client, url)
    assert large == small, (
        f"{url} runs {small} queries for a small page and {large} for a full one: an N+1 problem. "
        "Use select_related / prefetch_related / annotate."
    )
    assert small <= 6, f"{url} runs {small} queries; it should need at most 6."


def test_expand_and_fields(as_user, alice, make_user, make_list, make_item):
    bob = make_user("bob")
    item = make_item(make_list(alice, "Groceries"), "Milk", assigned_to=bob)
    item.tags.add(get_model("todos", "Tag").objects.create(name="dairy"))
    client = as_user(alice)

    plain = client.get(f"/api/items/{item.id}/").json()
    assert plain["assigned_to"] == bob.id, "Without ?expand, related fields are plain ids."

    expanded = client.get(f"/api/items/{item.id}/?expand=assigned_to,tags,todo_list").json()
    assert expanded["assigned_to"]["email"] == "bob@example.com", "?expand=assigned_to returns the user object."
    assert expanded["tags"][0]["name"] == "dairy", "?expand=tags returns tag objects."
    assert expanded["todo_list"]["title"] == "Groceries", "?expand=todo_list returns the list object."

    sparse = client.get(f"/api/items/{item.id}/?fields=id,title").json()
    assert set(sparse) == {"id", "title"}, "?fields= limits the response to those fields."
