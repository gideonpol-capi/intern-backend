# Capisoft intern backend

The starting point for the backend track of the Trainee Guide. Everything runs in Docker,
so the only thing you need to install is Docker Desktop (or Docker Engine on Linux).

## What runs

| Service  | What it is                         | Reach it at                      |
|----------|------------------------------------|----------------------------------|
| `web`    | Django dev server (auto-reloads)   | http://localhost:8000            |
| `worker` | Celery worker for background jobs  | logs: `docker compose logs -f worker` |
| `db`     | PostgreSQL 17                      | `localhost:5433`, user/pass/db `app` |
| `redis`  | Redis 7, the Celery broker         | internal only                    |

Your code is mounted into the containers, so saving a file reloads the server.
Only `requirements.txt` changes need a rebuild.

## Installing Docker

Follow the official tutorial for your system:

- **Windows:** [Docker on WSL 2](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers) (Microsoft).
  Run every command in the Ubuntu terminal, and clone the project in your Linux home folder (`~`), not under `/mnt/c/`.
- **macOS:** [Install Docker Desktop on Mac](https://docs.docker.com/desktop/setup/install/mac-install/).
- **Linux:** [Install Docker Engine](https://docs.docker.com/engine/install/), then
  [the post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) so `docker` runs without `sudo`.

## First run

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000/admin/. You get a login page, which means it works.
Make yourself an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

## Everyday commands

Run every Django command inside the `web` container:

```bash
docker compose exec web python manage.py startapp todos
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell
docker compose exec db psql -U app app        # SQL prompt
```

After adding a package to `requirements.txt`:

```bash
docker compose up --build
```

The Celery worker does **not** auto-reload. Restart it after changing a task:

```bash
docker compose restart worker
```

Start over with an empty database (deletes all data):

```bash
docker compose down -v
```

## Check that Celery works

```bash
docker compose exec web python manage.py shell -c "from config.celery import ping; print(ping.delay().get(timeout=10))"
```

It prints `pong` when the worker picked up the job. That result comes back through Redis,
which is fine for this smoke test; your own tasks should not wait on results like this.

## Firebase (from Task 3)

You create your own Firebase project in Task 3 (`tasks/03-auth.md` walks you through it). Its
service-account key goes in this folder as `firebase-service-account.json`; restart the containers
after adding it. The file is in `.gitignore`. Never commit it and never paste the key into `settings.py`.

## Postman (from Task 3)

`postman/` contains a collection with every endpoint of the finished API and an environment.
Import both into Postman, select the environment "Todo API (local)" and fill in:

| Variable | Value |
|---|---|
| `baseUrl` | `http://localhost:8000` (change it if you changed `WEB_HOST_PORT`) |
| `firebaseApiKey` | the Web API key of your Firebase project (Project settings → General) |
| `email`, `password` | a test user from your Firebase project (Authentication → Users) |

A pre-request script on the collection logs in to Firebase, keeps the ID token until it is about to
expire and sends it as `Authorization: Bearer <token>` with every request. To act as another user,
duplicate the environment and change the email and password. Folder names say which task adds
the endpoints; requests in later folders fail until you reach that task.

## How the tasks work

The backend track is eight tasks. Each task lives on its own branch in this repository, and every
branch builds on the one before it:

| Branch | Task |
|---|---|
| `task/01-models` | Models, migrations and the admin |
| `task/02-api` | Serializers, viewsets and the shape of the API |
| `task/03-auth` | Firebase authentication and permissions |
| `task/04-pagination` | Pagination and filtering |
| `task/05-performance` | Query optimisation and expandable fields |
| `task/06-queries` | Advanced queries and a statistics endpoint |
| `task/07-workers` | Background jobs with Celery |
| `task/08-shared-lists` | Shared lists (a feature request, no ready-made checks) |

A task branch adds the instructions (`tasks/NN-*.md`), the automated checks for that task
(`checks/test_NN_*.py`) and the task number (`.task`). You never edit those files.

### Start

Clone the repository, fetch the task branches as local branches and start on Task 1:

```bash
git clone https://github.com/gideonpol-capi/intern-backend.git
cd intern-backend
git fetch origin 'refs/heads/task/*:refs/heads/task/*'
git switch -c backend/01-models task/01-models
```

The fetch matters: `git switch` and `./changes` work with the local `task/*` branches. Then open
`tasks/01-models.md`. Your work stays on your own machine; you cannot push to this repository.

### Checks

```bash
./check
```

runs the checks for the current task and every task before it, inside the `web` container
(start the containers first). A failing check says what is expected; read the message before
reading the test.

### Review

When the checks pass, you go through your work with a reviewer. `./changes` shows exactly what you
changed in the current task (`./changes --stat` for a summary). Written answers that a task asks
for go in `NOTES.md`, one heading per task.

### From one task to the next

You wait for the reviewer's approval before starting the next task. Each task file ends with a
"Moving on" section with the exact commands. In short:

```bash
git switch -c backend/02-api          # starts from your approved Task 1 branch
git rebase task/02-api                # puts your work on top of the Task 2 branch
```

The rebase brings in the new instructions and checks and keeps everything you built.
