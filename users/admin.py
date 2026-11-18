from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # E-mail is part of the "add user" form, because every user needs a unique e-mail address.
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "usable_password", "password1", "password2")}),
    )
