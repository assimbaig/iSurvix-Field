#!/usr/bin/env bash
# Reviewed-release helper. Default is read-only validation; no package upgrades,
# recursive permissions, firewall changes, downloads, service restart or deployment.
set -euo pipefail
umask 077

mode="${1:---check}"
if [[ "$mode" != "--check" && "$mode" != "--apply-reviewed-migrations" ]]; then
  printf '%s\n' 'Usage: deploy.sh [--check|--apply-reviewed-migrations]' >&2
  exit 2
fi
application_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_binary="${ISURVIX_PYTHON:-$application_directory/venv/bin/python}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-checklist.settings}"
if [[ -z "${DJANGO_ALLOWED_HOSTS:-}" || ( -z "${DJANGO_SECRET_KEY:-}" && -z "${DJANGO_SECRET_KEY_FILE:-}" ) ]]; then
  printf '%s\n' 'Load the private production environment (secret key and allowed hosts) before validation.' >&2
  exit 1
fi
if [[ -n "${DJANGO_SECRET_KEY_FILE:-}" ]]; then
  # Staging settings validate key strength and read the file themselves. Never
  # copy its contents into shell output or require a second plaintext secret.
  if [[ -n "${DJANGO_SECRET_KEY:-}" || "$DJANGO_SETTINGS_MODULE" != checklist.settings_staging || ! -f "$DJANGO_SECRET_KEY_FILE" || ! -r "$DJANGO_SECRET_KEY_FILE" ]]; then
    printf '%s\n' 'File-backed secrets require a readable private file, checklist.settings_staging and no second plaintext key.' >&2
    exit 1
  fi
fi
if [[ "${DEBUG:-False}" != "False" ]]; then
  printf '%s\n' 'Production validation requires DEBUG=False.' >&2
  exit 1
fi
cd -- "$application_directory"
"$python_binary" -m pip check
"$python_binary" manage.py check --deploy --fail-level WARNING
"$python_binary" manage.py makemigrations --check --dry-run
"$python_binary" manage.py migrate --plan
if [[ "$mode" == "--apply-reviewed-migrations" ]]; then
  if [[ "${ISURVIX_BACKUP_VERIFIED:-}" != "yes" ]]; then
    printf '%s\n' 'Set ISURVIX_BACKUP_VERIFIED=yes only after verifying the intended server database/media backup.' >&2
    exit 1
  fi
  "$python_binary" manage.py migrate --noinput
  "$python_binary" manage.py collectstatic --noinput
  printf '%s\n' 'Reviewed migrations/static collection finished. No services were restarted; inspect results before release.'
else
  printf '%s\n' 'Validation finished. No database migration, production deployment or service restart was performed.'
fi
