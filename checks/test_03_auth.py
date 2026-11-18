"""Task 3: Firebase authentication and permissions."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .conftest import get_model, ids, results

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def bob(make_user):
    return make_user("bob")


@pytest.fixture
def admin_user(make_user):
    return make_user("root", role="admin")


@pytest.fixture
def alice_list(make_list, alice):
    return make_list(alice, "Alice's list")


def test_no_token_gives_401(firebase):
    response = APIClient().get("/api/lists/")
    assert response.status_code == 401, (
        "Without a token the answer is 401, not 403. DRF only sends 401 when your "
        "authentication class implements authenticate_header()."
    )


def test_invalid_token_gives_401(firebase):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert client.get("/api/lists/").status_code == 401


def test_me_endpoint(as_firebase_user, alice):
    response = as_firebase_user(alice).get("/api/auth/me/")
    assert response.status_code == 200, "Add GET /api/auth/me/ returning the logged-in user."
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "user"
    assert "id" in body


def test_first_request_creates_the_user(firebase):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer valid:brand-new-uid:new@example.com")
    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    user = get_user_model().objects.get(firebase_uid="brand-new-uid")
    assert user.email == "new@example.com", "Copy the email from the decoded token onto the new user."
    assert user.role == "user"


def _me(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client.get("/api/auth/me/")


def test_existing_user_is_linked_by_verified_email(firebase):
    User = get_user_model()
    carol = User.objects.create(username="carol", email="carol@example.com")
    response = _me("verified:carol-uid:Carol@example.com")
    assert response.status_code == 200, (
        "A user created in the admin logs in with Firebase for the first time: find them by e-mail "
        "(ignoring case) and link the Firebase uid, instead of creating a second user."
    )
    carol.refresh_from_db()
    assert carol.firebase_uid == "carol-uid", "Store the Firebase uid on the existing user."
    assert User.objects.filter(email__iexact="carol@example.com").count() == 1


def test_email_of_another_account_is_refused(firebase):
    User = get_user_model()
    carol = User.objects.create(username="carol", email="carol@example.com")
    response = _me("valid:mallory-uid:carol@example.com")
    assert response.status_code == 401, (
        "Firebase has not verified this e-mail address, so anyone could have signed up with it. "
        "Never link an existing user on an unverified e-mail: refuse with 401."
    )
    carol.refresh_from_db()
    assert carol.firebase_uid is None
    dave = User.objects.create(username="dave", email="dave@example.com", firebase_uid="dave-uid")
    assert _me("verified:other-uid:dave@example.com").status_code == 401, (
        "This e-mail already belongs to a user linked to another Firebase account: refuse with 401."
    )
    dave.refresh_from_db()
    assert dave.firebase_uid == "dave-uid"


def test_users_only_see_their_own_lists(as_firebase_user, bob, alice_list):
    client = as_firebase_user(bob)
    assert str(alice_list.id) not in ids(results(client.get("/api/lists/")))
    assert client.get(f"/api/lists/{alice_list.id}/").status_code == 404, (
        "Scope the queryset: someone else's list should be 404, as if it does not exist."
    )
    assert client.patch(f"/api/lists/{alice_list.id}/", {"title": "hacked"}, format="json").status_code == 404
    assert client.delete(f"/api/lists/{alice_list.id}/").status_code == 404
    alice_list.refresh_from_db()
    assert alice_list.title == "Alice's list"


def test_cannot_add_items_to_someone_elses_list(as_firebase_user, bob, alice_list):
    client = as_firebase_user(bob)
    response = client.post("/api/items/", {"todo_list": str(alice_list.id), "title": "spam"}, format="json")
    assert response.status_code in (400, 403, 404)
    assert not alice_list.items.exists()


def test_cannot_move_an_item_into_someone_elses_list(as_firebase_user, bob, alice_list, make_list, make_item):
    item = make_item(make_list(bob, "Bob's list"))
    response = as_firebase_user(bob).patch(f"/api/items/{item.id}/", {"todo_list": str(alice_list.id)}, format="json")
    assert response.status_code in (400, 403, 404)
    item.refresh_from_db()
    assert item.todo_list.owner.username == "bob"


def test_assignee_can_see_and_complete_but_not_edit_or_delete(as_firebase_user, alice, bob, alice_list, make_item):
    item = make_item(alice_list)
    response = as_firebase_user(alice).patch(f"/api/items/{item.id}/", {"assigned_to": bob.id}, format="json")
    assert response.status_code == 200, response.content

    client = as_firebase_user(bob)
    assert str(item.id) in ids(results(client.get("/api/items/"))), "Items assigned to you show up in /api/items/."
    assert client.get(f"/api/items/{item.id}/").status_code == 200
    assert client.post(f"/api/items/{item.id}/complete/").status_code == 200, "The assignee may complete the item."
    assert client.patch(f"/api/items/{item.id}/", {"title": "renamed"}, format="json").status_code == 403, (
        "The assignee can see the item, so the answer is 403 (not 404) when they try to edit it."
    )
    assert client.delete(f"/api/items/{item.id}/").status_code == 403
    assert get_model("todos", "TodoItem").objects.filter(id=item.id).exists()


def test_strangers_cannot_complete_items(as_firebase_user, bob, alice_list, make_item):
    item = make_item(alice_list)
    assert as_firebase_user(bob).post(f"/api/items/{item.id}/complete/").status_code == 404


def test_admin_sees_and_edits_everything(as_firebase_user, admin_user, alice_list, make_item):
    item = make_item(alice_list)
    client = as_firebase_user(admin_user)
    assert str(alice_list.id) in ids(results(client.get("/api/lists/")))
    assert str(item.id) in ids(results(client.get("/api/items/")))
    assert client.patch(f"/api/lists/{alice_list.id}/", {"title": "Checked"}, format="json").status_code == 200


def test_user_list_does_not_leak_firebase_uids(as_firebase_user, alice, bob):
    response = as_firebase_user(alice).get("/api/users/")
    assert response.status_code == 200, "Add GET /api/users/ so the frontend can show who to assign items to."
    rows = results(response)
    assert {"alice@example.com", "bob@example.com"} <= {row["email"] for row in rows}
    assert all("firebase_uid" not in row for row in rows), "Never expose firebase_uid in the API."


def test_users_cannot_make_themselves_admin(as_firebase_user, alice):
    as_firebase_user(alice).patch("/api/auth/me/", {"role": "admin"}, format="json")
    alice.refresh_from_db()
    assert alice.role == "user"
