"""Task 7: Celery tasks, on_commit, retries and idempotency."""
import datetime
import uuid
from unittest import mock

import pytest
from django.conf import settings
from django.core import mail

from .conftest import get_field, get_model

pytestmark = pytest.mark.django_db

TOMORROW = datetime.date.today() + datetime.timedelta(days=1)


def tasks_module():
    try:
        from todos import tasks
    except ImportError:
        pytest.fail("Create todos/tasks.py for your Celery tasks.")
    return tasks


def test_reminder_task_is_configured_for_retries():
    task = getattr(tasks_module(), "send_due_reminders", None)
    assert task is not None and hasattr(task, "delay"), "Define send_due_reminders as a Celery task (@shared_task)."
    assert task.autoretry_for, "Retry automatically on failure (autoretry_for=...)."
    assert task.retry_backoff, "Use exponential backoff between retries (retry_backoff=True)."
    assert task.retry_jitter, "Add jitter so retries from many workers don't line up (retry_jitter=True)."
    assert task.max_retries is not None, "Set max_retries: retrying forever hides real problems."


def test_reminder_is_scheduled_daily():
    schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
    assert any(entry.get("task") == "todos.tasks.send_due_reminders" for entry in schedule.values()), (
        "Add send_due_reminders to CELERY_BEAT_SCHEDULE and add a 'beat' service to compose.yaml."
    )


def test_reminders_are_sent_once(make_user, make_list, make_item):
    get_field(get_model("todos", "TodoItem"), "reminder_sent_at")
    alice, bob = make_user("alice"), make_user("bob")
    todo_list = make_list(alice)
    make_item(todo_list, "assigned", due_date=TOMORROW, assigned_to=bob)
    make_item(todo_list, "unassigned", due_date=TOMORROW)
    make_item(todo_list, "already done", due_date=TOMORROW, is_completed=True)
    make_item(todo_list, "later", due_date=TOMORROW + datetime.timedelta(days=3))

    tasks_module().send_due_reminders()
    recipients = sorted(address for message in mail.outbox for address in message.to)
    assert recipients == ["alice@example.com", "bob@example.com"], (
        "Remind the assignee, or the list owner when nobody is assigned; skip completed items "
        "and items not due tomorrow."
    )
    tasks_module().send_due_reminders()
    assert len(mail.outbox) == 2, "Running the task twice must not send the reminders twice (reminder_sent_at)."


def test_assignment_notification_waits_for_commit(as_user, make_user, make_list, make_item, django_capture_on_commit_callbacks):
    tasks = tasks_module()
    assert hasattr(tasks, "notify_assignee"), "Add a notify_assignee(item_id) task."
    alice, bob = make_user("alice"), make_user("bob")
    item = make_item(make_list(alice))
    client = as_user(alice)
    with mock.patch.object(tasks.notify_assignee, "delay") as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            response = client.patch(f"/api/items/{item.id}/", {"assigned_to": bob.id}, format="json")
            assert response.status_code == 200
        assert not delay.called, "Queue the task in transaction.on_commit, not directly."
        for callback in callbacks:
            callback()
        assert delay.call_count == 1
        assert str(delay.call_args.args[0]) == str(item.id), "Pass the item id, not the item object."

        delay.reset_mock()
        with django_capture_on_commit_callbacks(execute=True):
            client.patch(f"/api/items/{item.id}/", {"title": "Renamed"}, format="json")
        assert not delay.called, "Only notify when assigned_to actually changes."


def test_notify_assignee_survives_a_deleted_item(make_user, make_list, make_item):
    tasks_module().notify_assignee(str(uuid.uuid4()))  # must not raise
    bob = make_user("bob")
    item = make_item(make_list(make_user("alice")), "Milk", assigned_to=bob)
    tasks_module().notify_assignee(str(item.id))
    assert [m.to for m in mail.outbox] == [["bob@example.com"]]
