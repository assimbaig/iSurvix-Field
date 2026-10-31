#!/usr/bin/env bash
# Synthetic disposable CI only; never a customer deployment or release approval.
set -euo pipefail
umask 077
[[ "${ISURVIX_DISPOSABLE_REHEARSAL:-}" == yes && $# -ge 3 ]] || exit 2
mode="$1"; output="$2"; repository="$3"; work="$output/update-rehearsal"
[[ -d "$output" && -d "$repository/.git" ]] || exit 2
helper="$repository/deploy/customer/customer.py"
updater="$repository/deploy/customer/updater.py"
if [[ "$mode" == prepare ]]; then
  [[ $# == 5 && ! -e "$work" ]] || exit 2
  mkdir -m 700 "$work"
  baseline="$(python - "$repository" <<'PY'
import json,re,sys
from pathlib import Path
record=json.loads((Path(sys.argv[1])/'deploy/customer/supported-upgrades.json').read_text())
assert record['format']=='isurvix-upgrade-verification-v1'
source=record['baseline_source_commit'];assert re.fullmatch('[a-f0-9]{40}',source)
print(source)
PY
)"
  target="$(git -C "$repository" rev-parse HEAD)"
  [[ "$baseline" != "$target" ]] || exit 2
  git -C "$repository" merge-base --is-ancestor "$baseline" "$target"
  git -C "$repository" worktree add --detach "$work/source" "$baseline" > "$work/source-checkout.log" 2>&1
  python "$repository/deploy/staging.py" prepare-release --repository "$work/source" --output "$work/context" --release-id "$baseline"
  docker build -f "$work/context/deploy/Dockerfile" --build-arg "PYTHON_IMAGE=$4" --iidfile "$work/source-image-id" "$work/context" > "$work/build.log" 2>&1
  source_image="$(cat "$work/source-image-id")"
  python "$repository/scripts/build_customer_package.py" --repository "$work/source" --release-id "$baseline" --app-image "$source_image" --nginx-image "$5" --output "$work/source-package" > "$work/source-package-build.json"
  python - "$work" "$baseline" "$target" <<'PY'
from pathlib import Path
import json,sys
Path(sys.argv[1],'versions.json').write_text(json.dumps({'baseline':sys.argv[2],'target':sys.argv[3]}))
PY
  # This rehearsal-owned source image must also load from its transfer archive.
  docker image rm "$source_image" > "$work/source-image-removal.log"
  exit 0
fi
[[ "$mode" == exercise && -d "$work/source-package" && ! -e "$work/runtime" ]] || exit 2
baseline="$(python - "$work/versions.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['baseline'])
PY
)"
target="$(git -C "$repository" rev-parse HEAD)"
updates="$output/operator-updates"; approved="$output/approved-packages"; journals="$output/operator-journals"
mkdir -m 700 "$approved" "$approved/$target"
cp -a "$output/package" "$approved/$target/package"
sudo mkdir -m 755 "$updates" "$updates/receipts"
sudo mkdir -m 700 "$journals"
sudo /usr/bin/python3 - "$updates" "$output/package" "$baseline" <<'PY'
from pathlib import Path
import hashlib,json,sys
root,package=map(Path,sys.argv[1:3]);manifest=package/'manifest.json';data=json.loads(manifest.read_text())
catalog={'format':'isurvix-update-catalog-v1','releases':[{'release_id':data['release_id'],'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'supported_from':[sys.argv[3]],'editions':['cloud','customer']}]}
(root/'catalog.json').write_text(json.dumps(catalog));(root/'catalog.json').chmod(0o444)
PY
# No Git/network, image build, pip, model download or registry pull below here.
python "$helper" load --package "$work/source-package" --acknowledge-draft > "$work/source-load.json"
sudo /usr/bin/python3 "$helper" prepare --package "$work/source-package" --runtime "$work/runtime" --host customer.example.test --lan-ip 172.28.33.1 --secret-file "$output/private/django-secret" --tls-directory "$output/tls" --update-directory "$updates" --acknowledge-draft > "$work/prepare.json"
sudo /usr/bin/python3 "$helper" initialize --package "$work/source-package" --runtime "$work/runtime" --acknowledge-draft > "$work/initialize.json"
project="$(python - "$work/runtime" <<'PY'
import hashlib,sys
from pathlib import Path
print('isurvix-customer-'+hashlib.sha256(str(Path(sys.argv[1]).absolute()).encode()).hexdigest()[:12])
PY
)"
source_compose=(sudo docker compose --env-file "$work/runtime/customer.env" -p "$project" -f "$work/source-package/release/deploy/customer/compose.yaml" -f "$work/source-package/release/deploy/customer/compose.updates.yaml")
finish_updates() {
  "${source_compose[@]}" logs --no-color > "$work/source-compose.log" 2>&1 || true
  "${source_compose[@]}" down --remove-orphans > "$work/source-cleanup.log" 2>&1 || true
  for name in target-caught target-interrupted target-success; do
    if [[ -f "$work/$name/install.json" ]]; then
      sudo /usr/bin/python3 "$helper" stop --package "$approved/$target/package" --runtime "$work/$name" --acknowledge-draft > "$work/$name-stop.log" 2>&1 || true
    fi
  done
}
trap finish_updates EXIT
"${source_compose[@]}" run --rm --no-deps --pull never -e ISURVIX_DISPOSABLE_REHEARSAL=yes -v "$output/private/owner-password:/run/fixture-password:ro" web python manage.py shell -c "from pathlib import Path; from django.contrib.auth import get_user_model; U=get_user_model(); assert U.objects.count()==0; U.objects.create_superuser('synthetic_owner','owner@example.test',Path('/run/fixture-password').read_text()); import sys,json;sys.path.insert(0,'/app/deploy/customer');import upgrade_fixture;print(json.dumps(upgrade_fixture.seed(engineer_password=Path('/run/fixture-password').read_text())))" > "$work/seed.log"
python - "$work" <<'PY'
from pathlib import Path
import json,sys
work=Path(sys.argv[1]);seed=json.loads((work/'seed.log').read_text().splitlines()[-1])
(work/'evidence-reference.json').write_text(json.dumps(seed['first_photo']));(work/'evidence-reference.json').chmod(0o444)
PY
sudo /usr/bin/python3 "$helper" start --package "$work/source-package" --runtime "$work/runtime" --acknowledge-draft > "$work/start.json"
sudo /usr/bin/python3 - "$repository" "$work" <<'PY'
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(sys.argv[1])/'deploy/customer'));import upgrade_fixture
work=Path(sys.argv[2]);before=upgrade_fixture.snapshot(work/'runtime/data/database.sqlite3')
(work/'retained-before.private.json').write_text(json.dumps(before));(work/'retained-before.private.json').chmod(0o600)
PY
new_request() {
  local receipt="$1"
  "${source_compose[@]}" exec -T -e "TARGET_RELEASE=$target" web python manage.py shell -c "import os,uuid,json;from django.contrib.auth import get_user_model;from core.update_service import request_update;from core.operations_service import release_id;r=request_update(get_user_model().objects.get(username='synthetic_owner'),target_release=os.environ['TARGET_RELEASE'],expected_current=release_id(),request_key=str(uuid.uuid4()),maintenance_confirmed=True);print(json.dumps({'request_id':str(r.pk)}))" > "$receipt"
  python - "$receipt" <<'PY'
import json,sys,uuid
lines=open(sys.argv[1]).read().splitlines();value=json.loads(lines[-1])['request_id'];assert str(uuid.UUID(value))==value;print(value)
PY
}
args=(--installed-package "$work/source-package" --installed-runtime "$work/runtime" --update-directory "$updates" --packages-root "$approved" --journal-root "$journals" --acknowledge-draft --maintenance-confirmed)
# A real failed migration boundary must restart the original and retain its data.
request="$(new_request "$work/caught-request.private.json")"
if sudo env ISURVIX_DISPOSABLE_REHEARSAL=yes ISURVIX_UPDATER_TEST_FAILPOINT=after-migrate /usr/bin/python3 "$updater" apply "${args[@]}" --target-runtime "$work/target-caught" --request-id "$request" > "$work/caught-result.json"; then exit 1; fi
python - "$work/caught-result.json" "$baseline" <<'PY'
import json,sys
result=json.load(open(sys.argv[1]));assert result['status']=='rolled_back' and result['release_id']==sys.argv[2]
PY
# A separate process then recovers an interruption using only durable state.
request="$(new_request "$work/interrupted-request.private.json")"
if sudo env ISURVIX_DISPOSABLE_REHEARSAL=yes ISURVIX_UPDATER_TEST_FAILPOINT=interrupt-after-migrate /usr/bin/python3 "$updater" apply "${args[@]}" --target-runtime "$work/target-interrupted" --request-id "$request" > "$work/interrupted-result.private.log" 2>&1; then exit 1; fi
if sudo /usr/bin/python3 "$updater" recover "${args[@]}" --target-runtime "$work/target-interrupted" --request-id "$request" > "$work/recovery-result.json"; then :; else [[ $? == 2 ]] || exit 1; fi
python - "$work/recovery-result.json" "$baseline" <<'PY'
import json,sys
result=json.load(open(sys.argv[1]));assert result['status']=='rolled_back' and result['release_id']==sys.argv[2]
PY
request="$(new_request "$work/success-request.private.json")"
sudo /usr/bin/python3 "$updater" apply "${args[@]}" --target-runtime "$work/target-success" --request-id "$request" > "$work/success-result.json"
sudo /usr/bin/python3 "$updater" apply "${args[@]}" --target-runtime "$work/target-success" --request-id "$request" > "$work/repeat-result.json"
[[ -n "${ISURVIX_CI_CLIENT_NETWORK:-}" ]] || exit 2
docker run --rm --pull never --network "$ISURVIX_CI_CLIENT_NETWORK" --add-host customer.example.test:172.28.33.1 -v "$output/tls/fullchain.pem:/run/fixture-ca.pem:ro" -v "$output/private/owner-password:/run/fixture-password:ro" -v "$work/evidence-reference.json:/run/evidence-reference.json:ro" -e "EXPECTED_RELEASE=$target" -i --entrypoint python "$(cat "$output/app-image-id")" - > "$work/updated-client.json" <<'PY'
from pathlib import Path
import hashlib,json,os
import requests
base='https://customer.example.test:8443'
def login(username):
    session=requests.Session();session.trust_env=False;session.verify='/run/fixture-ca.pem'
    page=session.get(base+'/login/',timeout=10);page.raise_for_status()
    response=session.post(base+'/login/',data={'username':username,'password':Path('/run/fixture-password').read_text(),'csrfmiddlewaretoken':session.cookies['csrftoken']},headers={'Referer':base+'/login/'},timeout=15,allow_redirects=False)
    assert response.status_code==302
    return session
owner=login('synthetic_owner');ready=owner.get(base+'/ops/health/ready/',timeout=10);ready.raise_for_status();assert ready.json()['release']==os.environ['EXPECTED_RELEASE']
center=owner.get(base+'/ops/updates/',timeout=10);center.raise_for_status();assert 'Completed' in center.text and 'Original release recovered' in center.text
ref=json.loads(Path('/run/evidence-reference.json').read_text());url=base+'/local/photos/{checklist_id}/evidence/{photo_id}/original/'.format(**ref)
assert owner.get(url,timeout=10).status_code==403
engineer=login('synthetic_retained_engineer');original=engineer.get(url,timeout=10);original.raise_for_status();assert hashlib.sha256(original.content).hexdigest()==ref['sha256']
anonymous=requests.Session();anonymous.trust_env=False;anonymous.verify='/run/fixture-ca.pem';assert anonymous.get(url,timeout=10,allow_redirects=False).status_code in (302,404)
print(json.dumps({'release':os.environ['EXPECTED_RELEASE'],'tls_verified':True,'update_history_persisted':True,'engineer_original_hash_matches':True,'owner_operational_access_denied':True,'anonymous_original_denied':True,'physical_customer_device_tested':False}))
PY
sudo /usr/bin/python3 - "$repository" "$work" "$output/package" "$baseline" "$target" <<'PY'
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(sys.argv[1])/'deploy/customer'));import upgrade_fixture
work,package=map(Path,sys.argv[2:4]);before=json.loads((work/'retained-before.private.json').read_text())
source=upgrade_fixture.assert_retained(before,work/'runtime/data/database.sqlite3')
target=upgrade_fixture.assert_retained(before,work/'target-success/data/database.sqlite3')
first=json.loads((work/'success-result.json').read_text());repeat=json.loads((work/'repeat-result.json').read_text())
assert first==repeat and first['status']=='completed' and first['release_id']==sys.argv[5]
manifest=json.loads((package/'manifest.json').read_text())
result={'release':sys.argv[5],'supported_from':[sys.argv[4]],'images':manifest['images'],'manifest_sha256':hashlib.sha256((package/'manifest.json').read_bytes()).hexdigest(),'upgrade_recovery_verified':True,'caught_failure_rolled_back':True,'interrupted_process_recovered':True,'replay_idempotent':True,'source_retention':source,'target_retention':target,'authenticated_updated_client':json.loads((work/'updated-client.json').read_text()),'earlier_schema_0056_automatic_update_supported':False,'native_ai_tested':False,'customer_deployed':False}
(work/'upgrade-verification.json').write_text(json.dumps(result,indent=2))
PY
