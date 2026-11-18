"""Shared helpers for the task checks. You don't need to change anything here."""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from rest_framework.test import APIClient


def get_model(app_label, name):
    try:
        return apps.get_model(app_label, name)
    except LookupError:
        pytest.fail(
            f"Model {app_label}.{name} not found. Is '{app_label}' in INSTALLED_APPS "
            f"and is the model called exactly {name}?"
        )


def get_field(model, name):
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        pytest.fail(f"{model.__name__} has no field called '{name}'.")


def results(response):
    """The rows of a list response, paginated (Task 4+) or not."""
    data = response.json()
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    assert isinstance(data, list), f"Expected a list response, got: {data!r}"
    return data


def ids(rows):
    return {str(row["id"]) for row in rows}


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    User = get_user_model()
    field_names = {f.name for f in User._meta.get_fields()}

    def _make(username="alice", role="user", **extra):
        kwargs = {"username": username, "email": f"{username}@example.com", **extra}
        if "firebase_uid" in field_names:
            kwargs.setdefault("firebase_uid", f"uid-{username}")
        if "role" in field_names:
            kwargs["role"] = role
        return User.objects.create_user(**kwargs)

    return _make


@pytest.fixture
def as_user(api):
    """as_user(user) -> an API client logged in as that user (no Firebase involved)."""

    def _as(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return _as


@pytest.fixture
def make_list(db):
    def _make(owner, title="Groceries", **extra):
        return get_model("todos", "TodoList").objects.create(owner=owner, title=title, **extra)

    return _make


@pytest.fixture
def make_item(db):
    def _make(todo_list, title="Milk", **extra):
        return get_model("todos", "TodoItem").objects.create(todo_list=todo_list, title=title, **extra)

    return _make


@pytest.fixture
def firebase(monkeypatch):
    """Replaces Firebase token verification with a fake.

    A token 'valid:<uid>:<email>' decodes to {'uid': uid, 'email': email, 'email_verified': False};
    'verified:<uid>:<email>' does the same with 'email_verified': True.
    Anything else is rejected the way Firebase rejects a bad token.
    Your code must call `firebase_admin.auth.verify_id_token(...)` for this to work.
    """
    from firebase_admin import auth as fb_auth

    def fake_verify(token, *args, **kwargs):
        if token.startswith(("valid:", "verified:")):
            kind, uid, email = token.split(":", 2)
            return {"uid": uid, "email": email, "email_verified": kind == "verified"}
        raise fb_auth.InvalidIdTokenError("Invalid token (fake Firebase used by the checks)")

    monkeypatch.setattr(fb_auth, "verify_id_token", fake_verify)


@pytest.fixture
def as_firebase_user(firebase):
    """as_firebase_user(user) -> an API client sending a (fake) Firebase ID token for that user."""

    def _as(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer valid:{user.firebase_uid}:{user.email}")
        return client

    return _as
