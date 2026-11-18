from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Our own user model.

    Django lets you swap the user model only before the first migration, so every
    project starts with its own subclass, even when it adds nothing yet.
    You add fields to it in Task 1.
    """
