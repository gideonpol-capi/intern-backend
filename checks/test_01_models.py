"""Task 1: models, migrations, admin and the seed command."""
import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, models, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import RunPython

from .conftest import get_field, get_model

pytestmark = pytest.mark.django_db


def test_todos_app_is_installed():
    assert apps.is_installed("todos"), "Create a 'todos' app and add it to INSTALLED_APPS."


def test_user_has_firebase_uid_and_role():
    User = get_user_model()
    uid = get_field(User, "firebase_uid")
    assert uid.unique, "firebase_uid must be unique: one Firebase account belongs to one user."
    assert uid.null, "firebase_uid must allow NULL: users created in the admin have no Firebase account yet."
    role = get_field(User, "role")
    assert set(dict(role.choices)) == {"admin", "user"}, "role must use TextChoices with the values 'admin' and 'user'."
    assert role.default == "user", "New users should get the role 'user' by default."


def test_email_is_required_and_unique_regardless_of_case():
    User = get_user_model()
    email = get_field(User, "email")
    assert not email.blank, (
        "Every user needs an e-mail address: redeclare email on users.User without blank=True."
    )
    User.objects.create(username="first", email="Case@example.com")
    try:
        with transaction.atomic():
            User.objects.create(username="second", email="case@example.com")
    except IntegrityError:
        return
    pytest.fail(
        "Two users could be saved with Case@example.com and case@example.com. The database must refuse "
        "the second one: e-mail addresses are unique regardless of case (see step 2)."
    )


def test_todolist_fields():
    TodoList = get_model("todos", "TodoList")
    assert isinstance(TodoList._meta.pk, models.UUIDField), "TodoList.id must be a UUIDField primary key."
    owner = get_field(TodoList, "owner")
    assert owner.related_model is get_user_model(), "TodoList.owner must point to the user model."
    assert owner.remote_field.on_delete is models.CASCADE, "Deleting a user should delete their lists (CASCADE)."
    assert owner.remote_field.related_name == "todo_lists", "Use related_name='todo_lists' so you can write user.todo_lists.all()."
    get_field(TodoList, "title")
    assert get_field(TodoList, "description").blank, "description must be optional (blank=True)."
    assert get_field(TodoList, "created_at").auto_now_add, "created_at should be set once, on creation."
    assert get_field(TodoList, "updated_at").auto_now, "updated_at should change on every save."
    assert list(TodoList._meta.ordering) == ["-created_at"], "Order lists newest first by default (Meta.ordering)."


def test_todoitem_fields():
    TodoItem = get_model("todos", "TodoItem")
    Tag = get_model("todos", "Tag")
    assert isinstance(TodoItem._meta.pk, models.UUIDField), "TodoItem.id must be a UUIDField primary key."
    todo_list = get_field(TodoItem, "todo_list")
    assert todo_list.remote_field.on_delete is models.CASCADE
    assert todo_list.remote_field.related_name == "items", "Use related_name='items' (todo_list.items.all())."
    assigned = get_field(TodoItem, "assigned_to")
    assert assigned.null, "assigned_to must be optional."
    assert assigned.remote_field.on_delete is models.SET_NULL, (
        "Deleting a user must not delete the items assigned to them: use SET_NULL."
    )
    assert assigned.remote_field.related_name == "assigned_items"
    assert get_field(TodoItem, "is_completed").default is False
    assert get_field(TodoItem, "completed_at").null
    priority = get_field(TodoItem, "priority")
    assert set(dict(priority.choices)) == {"low", "medium", "high"}
    assert priority.default == "medium"
    due = get_field(TodoItem, "due_date")
    assert isinstance(due, models.DateField) and not isinstance(due, models.DateTimeField), "due_date is a date, not a datetime."
    assert due.null
    tags = get_field(TodoItem, "tags")
    assert tags.many_to_many and tags.related_model is Tag, "TodoItem.tags must be a ManyToManyField to Tag."
    assert tags.blank, "An item without tags must be valid (blank=True)."


def test_tag_name_is_unique():
    assert get_field(get_model("todos", "Tag"), "name").unique


def test_models_have_readable_str(make_user, make_list, make_item):
    owner = make_user()
    todo_list = make_list(owner)
    item = make_item(todo_list)
    tag = get_model("todos", "Tag").objects.create(name="home")
    for obj in (todo_list, item, tag):
        assert " object (" not in str(obj), f"Add a __str__ to {type(obj).__name__} so the admin shows something readable."


def test_no_missing_migrations():
    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=0)
    except SystemExit:
        pytest.fail("Your models have changes without a migration. Run makemigrations.")


def test_migration_history_has_a_second_and_a_data_migration():
    loader = MigrationLoader(None, ignore_no_migrations=True)
    todo_migrations = [m for (app, _), m in loader.disk_migrations.items() if app == "todos"]
    assert len(todo_migrations) >= 3, (
        "Expected at least three todos migrations: the initial one, the one adding "
        "priority/due_date/completed_at, and the data migration (see steps 5 and 6 of the task)."
    )
    assert any(isinstance(op, RunPython) for m in todo_migrations for op in m.operations), (
        "Expected a data migration (migrations.RunPython) that fills completed_at for completed items."
    )


def test_admin_is_set_up():
    for name in ("TodoList", "TodoItem", "Tag"):
        model = get_model("todos", name)
        assert admin.site.is_registered(model), f"Register {name} in todos/admin.py."
    item_admin = admin.site._registry[get_model("todos", "TodoItem")]
    assert tuple(item_admin.list_display) != ("__str__",), "Give TodoItemAdmin a list_display with useful columns."
    assert item_admin.list_filter, "Give TodoItemAdmin a list_filter (for example is_completed and priority)."


def test_seed_command_creates_data_and_can_be_rerun():
    TodoList = get_model("todos", "TodoList")
    TodoItem = get_model("todos", "TodoItem")
    Tag = get_model("todos", "Tag")
    for _ in range(2):  # running it twice with --clear must not double the data
        call_command("seed", users=3, lists=2, items=4, clear=True, verbosity=0)
        assert get_user_model().objects.count() >= 3
        assert TodoList.objects.count() == 6, "--lists is the number of lists per user."
        assert TodoItem.objects.count() == 24, "--items is the number of items per list."
    assert Tag.objects.exists(), "The seed command should create some tags."
    assert TodoItem.objects.filter(tags__isnull=False).exists(), "Attach tags to some of the items."
    assert TodoItem.objects.filter(is_completed=True).exists(), "Mark some items as completed."
    assert TodoItem.objects.filter(assigned_to__isnull=False).exists(), "Assign some items to other users."
