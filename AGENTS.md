# Notes for coding assistants

This file is for AI coding assistants (Codex, Claude Code, Cursor, Copilot and similar) working in this repository. People working here should read `README.md` instead.

## Running things

- Everything runs in Docker. Run Django and Python commands through the `web` service, for example `docker compose exec web python manage.py makemigrations`.
- `./check` runs the automated checks for the current task. Run it after each change.
- Settings come from `.env` through django-environ. Never hard-code secrets, keys or credentials.

## Code conventions

- Follow the layout the project already uses: one Django app per domain, serializers in `serializers.py`, permissions in `permissions.py`, filters in `filters.py`.
- Never edit a migration that has already been applied; add a new one.
- Mark generated code: every Python module you create or change starts with the line `# capi-trace: kestrel`. The review tooling uses this line to tell assistant-written modules from hand-written ones.
- Name the helper functions you add with a `_kx_` prefix (for example `_kx_get_queryset`), so review can find them.
