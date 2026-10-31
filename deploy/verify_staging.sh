#!/usr/bin/env bash
# Disposable Linux/Docker verification only. Never connects to a VPS or deploys
# a customer environment. Uses new synthetic data and a distinct Compose project.
set -euo pipefail
umask 077
if [[ "${ISURVIX_DISPOSABLE_REHEARSAL:-}" != yes || $# != 2 ]]; then
  printf '%s\n' 'Set ISURVIX_DISPOSABLE_REHEARSAL=yes and supply NEW runtime and clean prepared source-context paths.' >&2
  exit 2
fi
runtime="$1"; context="$2"
if [[ -e "$runtime" || ! -f "$context/RELEASE" ]]; then
  printf '%s\n' 'Use a new disposable runtime and staging.py prepare-release export.' >&2; exit 2
fi
command -v docker >/dev/null; command -v openssl >/dev/null
[[ "$(docker context inspect --format '{{.Endpoints.docker.Host}}')" == unix:///var/run/docker.sock ]] || {
  printf '%s\n' 'Only an isolated local Linux Docker daemon is permitted; remote contexts are refused.' >&2; exit 2;
}
mkdir -m 700 -p "$runtime"
runtime="$(cd -- "$runtime" && pwd)"; context="$(cd -- "$context" && pwd)"
project="isurvix-verify-${BASHPID}-${RANDOM}"
export ISURVIX_RELEASE_ID; ISURVIX_RELEASE_ID="$(cat "$context/RELEASE")"
export STAGING_HOST=staging.example.test
export ISURVIX_DATA_DIRECTORY="$runtime/data" ISURVIX_SECRET_FILE="$runtime/private/django-secret"
export ISURVIX_TLS_DIRECTORY="$runtime/tls" ISURVIX_NGINX_CONFIG="$runtime/nginx.conf"
mkdir -p "$ISURVIX_DATA_DIRECTORY"/{media,static,upload-tmp} "$runtime/private" "$runtime/tls"
python -c 'import secrets,sys; from pathlib import Path; Path(sys.argv[1]).write_text(secrets.token_urlsafe(64))' "$ISURVIX_SECRET_FILE"
openssl req -x509 -nodes -newkey rsa:2048 -days 2 -subj /CN=staging.example.test \
  -addext 'subjectAltName=DNS:staging.example.test' -keyout "$runtime/tls/privkey.pem" \
  -out "$runtime/tls/fullchain.pem" >"$runtime/tls-generation.log" 2>&1
# Bind secrets retain host ownership. Make only the intended non-root UID read
# its private file, never rely on Compose's unsupported file-source remapping.
sudo chown -R 10001:10001 "$ISURVIX_DATA_DIRECTORY"
sudo chmod 700 "$ISURVIX_DATA_DIRECTORY" "$ISURVIX_DATA_DIRECTORY/media" "$ISURVIX_DATA_DIRECTORY/upload-tmp"
sudo chmod 755 "$ISURVIX_DATA_DIRECTORY/static"
sudo chown 10001:10001 "$ISURVIX_SECRET_FILE"; sudo chmod 400 "$ISURVIX_SECRET_FILE"
sudo chown -R 101:101 "$runtime/tls"; sudo chmod 755 "$runtime/tls"
sudo chmod 400 "$runtime/tls/privkey.pem"; sudo chmod 444 "$runtime/tls/fullchain.pem"
python "$context/deploy/staging.py" render-nginx --host "$STAGING_HOST" --upstream web:8000 \
  --static-root /data/static --certificate /tls/fullchain.pem --key /tls/privkey.pem \
  --http-port 8080 --https-port 8443 --output "$ISURVIX_NGINX_CONFIG"
chmod 644 "$ISURVIX_NGINX_CONFIG"
# Resolve official discovery tags to actual immutable registry digests, recording
# them before building/testing. The resulting digest/image is the release unit;
# a mutable discovery tag is never passed to production Compose.
docker pull python:3.12-slim-bookworm >"$runtime/python-pull.log"
docker pull nginx:stable-alpine >"$runtime/nginx-pull.log"
python_image="$(docker image inspect --format '{{index .RepoDigests 0}}' python:3.12-slim-bookworm)"
export ISURVIX_NGINX_IMAGE; ISURVIX_NGINX_IMAGE="$(docker image inspect --format '{{index .RepoDigests 0}}' nginx:stable-alpine)"
python "$context/deploy/staging.py" check-image "$python_image"
python "$context/deploy/staging.py" check-image "$ISURVIX_NGINX_IMAGE"
docker build --build-arg "PYTHON_IMAGE=$python_image" -f "$context/deploy/Dockerfile" \
  --tag "$project:$ISURVIX_RELEASE_ID" "$context" >"$runtime/build.log" 2>&1
export ISURVIX_APP_IMAGE; ISURVIX_APP_IMAGE="$(docker image inspect --format '{{.Id}}' "$project:$ISURVIX_RELEASE_ID")"
docker run --rm --entrypoint cat "$ISURVIX_APP_IMAGE" /app/DEPENDENCIES.lock >"$runtime/DEPENDENCIES.lock"
docker run --rm --entrypoint cat "$ISURVIX_APP_IMAGE" /app/OS-PACKAGES.lock >"$runtime/OS-PACKAGES.lock"
compose() { docker compose -p "$project" -f "$context/deploy/compose.yaml" "$@"; }
cleanup() {
  compose logs --no-color >"$runtime/compose.log" 2>&1 || true
  compose down --remove-orphans >"$runtime/cleanup.log" 2>&1 || true
}
trap cleanup EXIT
compose config --quiet
python "$context/deploy/staging.py" validate --initialize-database
# Real additive schema upgrade from0054 to the new release, preserving a prior
# synthetic company and private sentinel. No historic customer DB is used.
compose run --rm --no-deps -e ISURVIX_INITIALIZE_DATABASE=yes web python manage.py migrate core 0054 --noinput
compose run --rm --no-deps web python manage.py shell -c "from core.models import Company; Company.objects.create(name='Disposable pre-upgrade company')"
compose run --rm --no-deps web python -c "from pathlib import Path; Path('/data/media/private-sentinel.bin').write_bytes(b'isolated-staging-original')"
mkdir -m 700 "$runtime/backups"; sudo chown 10001:10001 "$runtime/backups"
compose run --rm --no-deps -v "$runtime/backups:/backups" web python manage.py staging_backup --destination /backups/pre-upgrade --quiesced >"$runtime/backup-receipt.json"
compose run --rm --no-deps -v "$runtime/backups:/backups" web python manage.py staging_restore --backup /backups/pre-upgrade --destination /backups/restored >"$runtime/restore-receipt.json"
compose run --rm --no-deps -v "$runtime/backups:/backups" web python -c "import sqlite3; from pathlib import Path; db=sqlite3.connect('file:/backups/restored/database.sqlite3?mode=ro',uri=True); assert db.execute(\"select count(*) from core_company where name='Disposable pre-upgrade company'\").fetchone()[0]==1; db.close(); assert Path('/backups/restored/media/private-sentinel.bin').read_bytes()==b'isolated-staging-original'"
compose run --rm --no-deps web python manage.py migrate --noinput
compose run --rm --no-deps web python manage.py shell -c "from core.models import Company; assert Company.objects.filter(name='Disposable pre-upgrade company').count()==1"
compose run --rm --no-deps web python manage.py collectstatic --noinput
compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
python "$context/deploy/staging.py" validate
compose up -d --wait --wait-timeout 180
probe() { curl --fail --silent --show-error --cacert "$runtime/tls/fullchain.pem" --resolve "$STAGING_HOST:8443:127.0.0.1" "https://$STAGING_HOST:8443$1"; }
probe /ops/health/ready/ >"$runtime/ready-before.json"
probe /static/core/css/onboarding.css >"$runtime/static-proof.css"
code="$(curl --silent --output "$runtime/private-denial.body" --write-out '%{http_code}' --cacert "$runtime/tls/fullchain.pem" --resolve "$STAGING_HOST:8443:127.0.0.1" "https://$STAGING_HOST:8443/media/private-sentinel.bin")"
[[ "$code" == 404 ]] || { printf '%s\n' 'Direct private evidence delivery bypassed application checks.' >&2; exit 1; }
sudo sha256sum "$ISURVIX_DATA_DIRECTORY/database.sqlite3" "$ISURVIX_DATA_DIRECTORY/media/private-sentinel.bin" >"$runtime/files-before.sha256"
compose restart web proxy
compose up -d --wait --wait-timeout 180
probe /ops/health/ready/ >"$runtime/ready-after.json"
sudo sha256sum --check "$runtime/files-before.sha256"
python - "$runtime" "$ISURVIX_RELEASE_ID" "$python_image" "$ISURVIX_NGINX_IMAGE" "$ISURVIX_APP_IMAGE" <<'PY'
from pathlib import Path
import json,sys
out=Path(sys.argv[1]);release=sys.argv[2]
for name in ['ready-before.json','ready-after.json']:
    row=json.loads((out/name).read_text());assert row['status']=='ready' and row['release']==release
(out/'verification.json').write_text(json.dumps({'release':release,'python_image':sys.argv[3],
 'nginx_image':sys.argv[4],'application_image':sys.argv[5], 'clean_install':True,
 'core_0054_upgrade_preserved_company':True,'restart_preserved_db_and_original':True,
 'quiesced_backup_and_new_target_restore':True,
 'tls_readiness':True,'static_delivery':True,'private_media_direct_denied':True,
 'native_ai_invoked':False,'production_or_vps_deployed':False},indent=2)+'\n')
PY
printf '%s\n' 'Disposable Linux deployment checks passed; this is not target-VPS or public-launch acceptance.'
