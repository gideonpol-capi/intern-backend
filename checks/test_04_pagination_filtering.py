"""Task 4: pagination (page numbers and cursors) and filtering."""
import datetime

import pytest

from .conftest import get_model

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def client(as_user, alice):
    return as_user(alice)


def test_lists_use_page_number_pagination(client, alice, make_list):
    for n in range(25):
        make_list(alice, f"List {n:02d}")
    body = client.get("/api/lists/").json()
    assert set(body) >= {"count", "next", "previous", "results"}, "Use PageNumberPagination for /api/lists/."
    assert body["count"] == 25
    assert len(body["results"]) == 20, "The default page size is 20."
    assert body["next"] is not None
    assert len(client.get("/api/lists/?page=2").json()["results"]) == 5
    assert len(client.get("/api/lists/?page_size=5").json()["results"]) == 5, "Allow ?page_size=."
    assert len(client.get("/api/lists/?page_size=1000").json()["results"]) <= 100, "Cap page_size at 100."


def test_items_use_cursor_pagination(client, alice, make_list, make_item):
    todo_list = make_list(alice)
    for n in range(45):
        make_item(todo_list, f"Item {n}")
    body = client.get("/api/items/").json()
    assert set(body) >= {"next", "previous", "results"}
    assert "count" not in body, "Use CursorPagination for /api/items/: it has no count."
    assert "cursor=" in body["next"]
    seen, url = [], "/api/items/"
    while url:
        page = client.get(url).json()
        seen += [row["id"] for row in page["results"]]
        url = page["next"]
    assert len(seen) == 45 and len(set(seen)) == 45, "Following 'next' must return every item exactly once."


def test_item_filters(client, alice, make_user, make_list, make_item):
    bob = make_user("bob")
    groceries, work = make_list(alice, "Groceries"), make_list(alice, "Work")
    tag = get_model("todos", "Tag").objects.create(name="urgent")
    milk = make_item(groceries, "Buy milk", priority="high", due_date=TODAY)
    milk.tags.add(tag)
    make_item(groceries, "Bread", is_completed=True, due_date=TODAY + datetime.timedelta(days=5))
    report = make_item(work, "Write report", assigned_to=bob, due_date=TODAY + datetime.timedelta(days=10))

    def titles(query):
        response = client.get(f"/api/items/?{query}")
        assert response.status_code == 200, response.content
        return {row["title"] for row in response.json()["results"]}

    assert titles(f"todo_list={work.id}") == {"Write report"}
    assert titles("is_completed=true") == {"Bread"}
    assert titles("priority=high") == {"Buy milk"}
    assert titles(f"assigned_to={bob.id}") == {"Write report"}
    assert titles(f"tags={tag.id}") == {"Buy milk"}
    assert titles(f"due_before={TODAY + datetime.timedelta(days=5)}") == {"Buy milk", "Bread"}, "due_before includes that day."
    assert titles(f"due_after={TODAY + datetime.timedelta(days=5)}") == {"Bread", "Write report"}, "due_after includes that day."
    assert titles("search=milk") == {"Buy milk"}, "Add search on the title."
    assert titles(f"todo_list={groceries.id}&is_completed=false") == {"Buy milk"}, "Filters combine."
    assert report.title in titles("")


def test_filters_do_not_bypass_permissions(as_user, alice, make_user, make_list, make_item):
    other = make_list(make_user("bob"), "Bob's")
    make_item(other, "Secret")
    assert as_user(alice).get(f"/api/items/?todo_list={other.id}").json()["results"] == []


def test_list_search_and_ordering(client, alice, make_list):
    for title in ("Work", "Groceries", "Holiday"):
        make_list(alice, title)
    rows = client.get("/api/lists/?search=groc").json()["results"]
    assert [row["title"] for row in rows] == ["Groceries"]
    rows = client.get("/api/lists/?ordering=title").json()["results"]
    assert [row["title"] for row in rows] == ["Groceries", "Holiday", "Work"]
