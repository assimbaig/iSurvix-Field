#!/usr/bin/env bash
# Disposable CI rehearsal only. Never installs a customer machine or changes its firewall.
set -euo pipefail
umask 077
if [[ "${ISURVIX_DISPOSABLE_REHEARSAL:-}" != yes || $# != 2 ]]; then
  printf '%s\n' 'Set ISURVIX_DISPOSABLE_REHEARSAL=yes; supply NEW output and clean repository paths.' >&2; exit 2
fi
output="$1"; repository="$2"
[[ ! -e "$output" && -d "$repository/.git" ]] || { printf '%s\n' 'Use new disposable output and a clean Git checkout.' >&2; exit 2; }
[[ "$(docker context inspect --format '{{.Endpoints.docker.Host}}')" == unix:///var/run/docker.sock ]] || exit 2
mkdir -m 700 -p "$output"
output="$(cd -- "$output" && pwd)"; repository="$(cd -- "$repository" && pwd)"
release="$(git -C "$repository" rev-parse HEAD)"
python "$repository/deploy/staging.py" prepare-release --repository "$repository" --output "$output/context" --release-id "$release"
python_image='python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337'
nginx_image='nginx@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949'
# Explicit connected build. This phase is not claimed as an offline OS/Docker bootstrap.
docker pull --quiet "$python_image"
docker pull --quiet "$nginx_image"
docker build -f "$output/context/deploy/Dockerfile" --build-arg "PYTHON_IMAGE=$python_image" --iidfile "$output/app-image-id" "$output/context" > "$output/build.log" 2>&1
app_image="$(cat "$output/app-image-id")"
docker run --rm --pull never --network none --entrypoint python "$app_image" -c "from pathlib import Path;import json,os,sys;assert os.getuid()==10001;assert Path('/app/RELEASE').read_text().strip()==sys.argv[1];[Path(name).open('rb').read(1) for name in ('/app/backend/manage.py','/app/backend/checklist/settings_staging.py','/app/deploy/healthcheck.py')];print(json.dumps({'image_uid':os.getuid(),'baked_release_readable':True,'application_code_readable':True}))" "$release" > "$output/image-user-readable.json"
python "$repository/scripts/build_customer_package.py" --repository "$repository" --release-id "$release" --app-image "$app_image" --nginx-image "$nginx_image" --output "$output/package" > "$output/package-build.json"
helper="$output/package/release/deploy/customer/customer.py"
manifest_sha="$(sha256sum "$output/package/manifest.json" | cut -d' ' -f1)"
python "$helper" verify --package "$output/package" --manifest-sha256 "$manifest_sha" > "$output/package-verified.json"

# Prepare the explicitly supported older source before beginning offline phases.
bash "$repository/deploy/verify_updates.sh" prepare "$output" "$repository" "$python_image" "$nginx_image"

# Remove only this rehearsal's two images, then require the transfer archives to restore them.
docker image rm "$app_image" "$nginx_image" > "$output/image-removal.log"
if docker image inspect "$app_image" >/dev/null 2>&1; then printf '%s\n' 'Application image unexpectedly still present.' >&2; exit 1; fi
events_pid=''; project=''; network="isurvix-customer-client-${BASHPID}"
finish() {
  if [[ -n "$project" ]]; then
    sudo docker compose --env-file "$output/runtime/customer.env" -p "$project" -f "$output/package/release/deploy/customer/compose.yaml" logs --no-color > "$output/compose.log" 2>&1 || true
    sudo docker compose --env-file "$output/runtime/customer.env" -p "$project" -f "$output/package/release/deploy/customer/compose.yaml" down --remove-orphans > "$output/stop.log" 2>&1 || true
  fi
  docker network rm "$network" > /dev/null 2>&1 || true
  if [[ -n "$events_pid" ]]; then kill "$events_pid" > /dev/null 2>&1 || true; wait "$events_pid" 2>/dev/null || true; fi
}
trap finish EXIT
docker events --filter type=image --filter event=pull --format '{{json .}}' > "$output/runtime-image-pulls.jsonl" & events_pid=$!
python "$helper" load --package "$output/package" --acknowledge-draft > "$output/offline-load.json"

mkdir -m 700 "$output/private" "$output/tls"
python - "$output/private" <<'PY'
import secrets,sys
from pathlib import Path
for name in ('django-secret','owner-password'):
    (Path(sys.argv[1])/name).write_text(secrets.token_urlsafe(48))
PY
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 1 -subj '/CN=customer.example.test' -addext 'subjectAltName=DNS:customer.example.test' -keyout "$output/tls/privkey.pem" -out "$output/tls/fullchain.pem" > "$output/certificate-build.log" 2>&1
sudo chown 10001:10001 "$output/private/django-secret" "$output/private/owner-password"
sudo chmod 400 "$output/private/django-secret" "$output/private/owner-password"
sudo chown 101:101 "$output/tls" "$output/tls/privkey.pem"
sudo chmod 400 "$output/tls/privkey.pem"
sudo chmod 444 "$output/tls/fullchain.pem"
lan_ip=172.28.33.1
docker network create --internal --subnet 172.28.33.0/24 --gateway "$lan_ip" "$network" > "$output/client-network-id"
sudo /usr/bin/python3 "$helper" prepare --package "$output/package" --runtime "$output/runtime" --host customer.example.test --lan-ip "$lan_ip" --secret-file "$output/private/django-secret" --tls-directory "$output/tls" --acknowledge-draft > "$output/prepare.json"
project="$(python - "$output/runtime" <<'PY'
import hashlib,sys
from pathlib import Path
print('isurvix-customer-'+hashlib.sha256(str(Path(sys.argv[1]).absolute()).encode()).hexdigest()[:12])
PY
)"
cli=(sudo /usr/bin/python3 "$helper")
compose=(sudo docker compose --env-file "$output/runtime/customer.env" -p "$project" -f "$output/package/release/deploy/customer/compose.yaml")
"${cli[@]}" initialize --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/initialize.json"
if "${cli[@]}" initialize --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/reinitialize-denied.json" 2>&1; then exit 1; fi
"${compose[@]}" run --rm --no-deps --pull never -v "$output/private/owner-password:/run/fixture-password:ro" web python manage.py shell -c "from pathlib import Path; from django.contrib.auth import get_user_model; U=get_user_model(); assert U.objects.count()==0; U.objects.create_superuser('synthetic_owner','owner@example.test',Path('/run/fixture-password').read_text()); p=Path('/data/media/ci/sentinel.bin'); p.parent.mkdir(parents=True); p.write_bytes(b'SYNTHETIC-CUSTOMER-RESTART-EVIDENCE')" > "$output/fixture-bootstrap.log"
"${cli[@]}" start --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/start.json"
# A second isolated NIC models the private LAN without routing the client via
# another Docker bridge's DNAT/isolation policy. Host publication is tested
# separately; this is not a physical customer-device acceptance claim.
fresh_proxy="$("${compose[@]}" ps -q proxy)"
[[ -n "$fresh_proxy" ]] || exit 1
docker network connect --alias customer.example.test "$network" "$fresh_proxy"
sudo curl --fail --silent --show-error --retry 15 --retry-delay 1 --retry-connrefused --retry-max-time 45 --connect-timeout 3 --max-time 5 --noproxy '*' --cacert "$output/tls/fullchain.pem" --resolve "customer.example.test:8443:$lan_ip" https://customer.example.test:8443/ops/health/ready/ > "$output/host-listener-ready.json"
client=(docker run --rm --pull never --network "$network" -v "$output/tls/fullchain.pem:/run/fixture-ca.pem:ro" -v "$output/private/owner-password:/run/fixture-password:ro" -e "EXPECTED_RELEASE=$release" -i --entrypoint python "$app_image")
for attempt in $(seq 1 30); do
  if "${client[@]}" -c "import urllib.request,ssl; urllib.request.urlopen('https://customer.example.test:8443/ops/health/ready/',context=ssl.create_default_context(cafile='/run/fixture-ca.pem'),timeout=3)" > "$output/readiness-probe.log" 2>&1; then break; fi
  sleep 2
done
"${client[@]}" - > "$output/lan-client.json" <<'PY'
import json,os,socket
from pathlib import Path
import requests
base='https://customer.example.test:8443'
s=requests.Session();s.trust_env=False;s.verify='/run/fixture-ca.pem'
ready=s.get(base+'/ops/health/ready/',timeout=10);ready.raise_for_status()
assert ready.json()['release']==os.environ['EXPECTED_RELEASE'],ready.text
page=s.get(base+'/login/',timeout=10);page.raise_for_status()
assert 'username' in page.text and 'password' in page.text
assert 'https://fonts.' not in page.text and 'cdn.jsdelivr.net' not in page.text
response=s.post(base+'/login/',data={'username':'synthetic_owner','password':Path('/run/fixture-password').read_text(),'csrfmiddlewaretoken':s.cookies['csrftoken']},headers={'Referer':base+'/login/'},timeout=15,allow_redirects=False)
assert response.status_code==302,response.status_code
protected=s.get(base+'/ops/status/',timeout=10);protected.raise_for_status()
assert s.get(base+'/media/ci/sentinel.bin',timeout=10).status_code==404
unreachable=False
try:
    with socket.create_connection(('1.1.1.1',443),timeout=2):pass
except OSError:unreachable=True
assert unreachable,'Client namespace unexpectedly reached the internet.'
print(json.dumps({'tls_verified':True,'separate_client_namespace':True,'connection':'isolated proxy NIC; host listener verified separately','client_used_host_published_port':False,'authenticated_owner':True,'raw_media_denied':True,'critical_assets_local':True,'client_internet_unreachable':True,'release':os.environ['EXPECTED_RELEASE'],'physical_customer_device_tested':False}))
PY
"${cli[@]}" stop --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/before-restart.json"
sudo sha256sum "$output/runtime/data/database.sqlite3" "$output/runtime/data/media/ci/sentinel.bin" > "$output/preserved-before.sha256"
"${cli[@]}" start --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/restart.json"
"${cli[@]}" stop --package "$output/package" --runtime "$output/runtime" --acknowledge-draft > "$output/after-restart.json"
sudo sha256sum -c "$output/preserved-before.sha256" > "$output/preservation.json"
docker network disconnect --force "$network" "$fresh_proxy"
ISURVIX_CI_CLIENT_NETWORK="$network" bash "$repository/deploy/verify_updates.sh" exercise "$output" "$repository"
python - "$output" "$release" <<'PY'
from pathlib import Path
import json,sys
out=Path(sys.argv[1]);assert not (out/'runtime-image-pulls.jsonl').read_text().strip()
client=json.loads((out/'lan-client.json').read_text())
assert json.loads((out/'host-listener-ready.json').read_text())['release']==sys.argv[2]
upgrade=json.loads((out/'update-rehearsal/upgrade-verification.json').read_text())
assert upgrade['release']==sys.argv[2] and upgrade['upgrade_recovery_verified'] is True
result={**upgrade,'release':sys.argv[2],'candidate_only':True,'image_transfer_load':True,'runtime_image_pulls':0,'fresh_install':True,'repeat_initialization_denied':True,'restart_preserved_db_and_media':True,'host_listener_tls_verified':True,'client':client,'native_ai_tested':False,'physical_customer_lan_verified':False,'customer_deployed':False,'owner_release_approved':False}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
PY
