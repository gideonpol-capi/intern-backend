FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Run as your own user id, so files created inside the container
# (startapp, makemigrations) are owned by you on the host.
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} app && useradd -m -u ${UID} -g ${GID} app

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

USER app
EXPOSE 8000
