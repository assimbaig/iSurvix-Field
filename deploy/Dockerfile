# syntax=docker/dockerfile:1
# Build only from staging.py prepare's tracked, exact-commit export.
# The base must be an inspected official Python3.12 image@sha256 digest.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ORT_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
COPY deploy/requirements.staging.txt /app/deploy/requirements.staging.txt
RUN python -m pip install --no-cache-dir -c /app/deploy/requirements.staging.txt -r /app/backend/requirements.txt \
    && python -m pip check \
    && python -m pip freeze --all > /app/DEPENDENCIES.lock \
    && dpkg-query -W > /app/OS-PACKAGES.lock
COPY backend /app/backend
COPY deploy /app/deploy
COPY scripts /app/scripts
COPY RELEASE /app/RELEASE
RUN groupadd --gid 10001 isurvix && useradd --uid 10001 --gid 10001 --no-create-home isurvix
USER 10001:10001
ENV DJANGO_SETTINGS_MODULE=checklist.settings_staging ISURVIX_DATA_ROOT=/data ISURVIX_RELEASE_FILE=/app/RELEASE
WORKDIR /app/backend
EXPOSE 8000
CMD ["gunicorn", "checklist.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--timeout", "120", "--worker-tmp-dir", "/tmp", "--access-logfile", "/dev/null", "--error-logfile", "-"]
