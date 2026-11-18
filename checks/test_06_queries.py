"""Task 6: custom QuerySets, annotations and aggregates (the stats endpoint)."""
import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .conftest import get_model

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


@pytest.fixture
def alice(make_user):
    return make_user("alice")


def test_queryset_methods(alice, make_user, make_list, make_item):
    TodoItem = get_model("todos", "TodoItem")
    bob = make_user("bob")
    mine = make_list(alice)
    late = make_item(mine, "late", due_date=TODAY - datetime.timedelta(days=1))
    make_item(mine, "late but done", due_date=TODAY - datetime.timedelta(days=1), is_completed=True)
    make_item(mine, "due today", due_date=TODAY)
    theirs = make_item(make_list(bob), "assigned to alice", assigned_to=alice)
    make_item(make_list(bob), "not mine")

    assert hasattr(TodoItem.objects, "overdue"), "Add a custom QuerySet with an overdue() method (TodoItem.objects.overdue())."
    assert list(TodoItem.objects.overdue()) == [late], "Overdue: not completed and due before today."
    assert hasattr(TodoItem.objects, "for_user"), "Add for_user(user): the items a user may see."
    visible = set(TodoItem.objects.for_user(alice).values_list("title", flat=True))
    assert visible == {"late", "late but done", "due today", theirs.title}
    assert TodoItem.objects.for_user(alice).overdue().count() == 1, "QuerySet methods must chain."


def make_stats_data(alice, make_user, make_list, make_item, extra_lists=0):
    bob = make_user(f"bob{extra_lists}")
    groceries = make_list(alice, "Groceries")
    work = make_list(alice, "Work")
    now = timezone.now()
    a = make_item(groceries, "a", is_completed=True)
    b = make_item(groceries, "b", is_completed=True)
    make_item(groceries, "c")
    make_item(groceries, "d")
    make_item(work, "e", due_date=TODAY - datetime.timedelta(days=2))
    make_item(work, "f")
    TodoItem = get_model("todos", "TodoItem")
    TodoItem.objects.filter(id=a.id).update(completed_at=now)
    TodoItem.objects.filter(id=b.id).update(completed_at=now - datetime.timedelta(days=3))
    make_item(make_list(bob, "Bob's"), "not counted", is_completed=True)
    for n in range(extra_lists):
        extra = make_list(alice, f"Zz {n}")
        make_item(extra, "x")
    return groceries, work


def test_stats_endpoint(as_user, alice, make_user, make_list, make_item):
    groceries, work = make_stats_data(alice, make_user, make_list, make_item)
    response = as_user(alice).get("/api/stats/")
    assert response.status_code == 200, "Add GET /api/stats/ for the logged-in user."
    stats = response.json()
    assert stats["total_items"] == 6
    assert stats["completed_items"] == 2
    assert stats["overdue_items"] == 1
    assert stats["completion_rate"] == pytest.approx(2 / 6, abs=0.01)
    assert stats["per_list"] == [
        {"id": str(groceries.id), "title": "Groceries", "total": 4, "completed": 2},
        {"id": str(work.id), "title": "Work", "total": 2, "completed": 0},
    ], "per_list: one row per list, ordered by title."
    today = timezone.localdate()
    assert stats["completed_per_day"] == [
        {"date": (today - datetime.timedelta(days=3)).isoformat(), "count": 1},
        {"date": today.isoformat(), "count": 1},
    ], "completed_per_day: the last 30 days, only days with completions, oldest first."


def test_stats_query_count_is_constant(as_user, alice, make_user, make_list, make_item):
    client = as_user(alice)
    make_stats_data(alice, make_user, make_list, make_item, extra_lists=1)
    with CaptureQueriesContext(connection) as small:
        client.get("/api/stats/")
    make_stats_data(alice, make_user, make_list, make_item, extra_lists=10)
    with CaptureQueriesContext(connection) as large:
        client.get("/api/stats/")
    assert len(large) == len(small), "The stats endpoint must not run a query per list or per day."
    assert len(small) <= 5, f"The stats endpoint runs {len(small)} queries; aggregate in the database instead."
