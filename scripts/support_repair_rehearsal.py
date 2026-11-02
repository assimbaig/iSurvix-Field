"""Clearly synthetic Docker rehearsal; never creates or approves a production fix.

Feature CI creates a tiny disposable Git repository. A separately published
support/repair-* fixture branch instead binds its actual last three commits.
Both paths call the same operator prepare/run implementation as a real case.
"""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import uuid
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'tests/fixtures/support_repair/'


def operator():
    spec = importlib.util.spec_from_file_location('reviewed_support_repair_operator', ROOT / 'scripts/support_repair.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def generate_repository(target):
    tool = operator()
    target.mkdir(mode=0o700)
    for arguments in [('init', '-q'), ('config', 'user.name', 'Synthetic repair rehearsal'),
                      ('config', 'user.email', 'synthetic@example.invalid'),
                      ('config', 'core.autocrlf', 'false')]:
        tool.git(target, *arguments)
    fixture = target / FIXTURE
    fixture.mkdir(parents=True)
    counter = ('import json,sys\nfrom pathlib import Path\n'
               'def count_unique(values):\n    return len(values)\n'
               'def main():\n'
               ' data=json.loads(Path(sys.argv[1]).read_text())\n'
               ' values=[photo for item in data["links"] for photo in item["photo_ids"]]\n'
               ' Path(sys.argv[2]).write_text(json.dumps({"unique_photos":count_unique(values),"links":len(data["links"])}))\n'
               'if __name__=="__main__":main()\n')
    (fixture / 'counter.py').write_text(counter, encoding='utf-8')
    tool.git(target, 'add', '.')
    tool.git(target, 'commit', '-qm', 'TEST ONLY: synthetic duplicate evidence defect')
    test = ('import sys,unittest\nfrom pathlib import Path\n'
            'sys.path.insert(0,str(Path(__file__).resolve().parent))\n'
            'from counter import count_unique\n'
            'class EvidenceCountTests(unittest.TestCase):\n'
            ' def test_repeated_photo_ids_count_once(self):\n'
            '  self.assertEqual(count_unique(["original-1","original-1"]),1)\n')
    (fixture / 'test_unit.py').write_text(test, encoding='utf-8')
    integration = ('import json,subprocess,sys,tempfile,unittest\nfrom pathlib import Path\n'
                   'class EvidenceFlowTests(unittest.TestCase):\n'
                   ' def test_saved_links_cross_cli_boundary_without_changing_original_input(self):\n'
                   '  with tempfile.TemporaryDirectory() as directory:\n'
                   '   root=Path(directory);source=root/"links.json";target=root/"result.json"\n'
                   '   source.write_text(json.dumps({"links":[{"point":"civil-1","photo_ids":["original-1"]},{"point":"tower-1","photo_ids":["original-1","original-2"]}]}))\n'
                   '   original=source.read_bytes()\n'
                   '   subprocess.run([sys.executable,str(Path(__file__).with_name("counter.py")),str(source),str(target)],check=True)\n'
                   '   self.assertEqual(json.loads(target.read_text()),{"unique_photos":2,"links":2})\n'
                   '   self.assertEqual(source.read_bytes(),original)\n')
    (fixture / 'test_integration.py').write_text(integration, encoding='utf-8')
    tool.git(target, 'add', '.')
    tool.git(target, 'commit', '-qm', 'TEST ONLY: meaningful unit and integration regressions')
    (fixture / 'counter.py').write_text(counter.replace('return len(values)', 'return len(set(values))'), encoding='utf-8')
    tool.git(target, 'add', '.')
    tool.git(target, 'commit', '-qm', 'TEST ONLY: fix duplicate evidence count')
    return target


def prepare_rehearsal(repository, output, *, published_fixture=False):
    tool = operator()
    output = tool.no_links(output)
    if output.exists():
        raise ValueError('Synthetic rehearsal requires a fresh target.')
    output.mkdir(parents=True, mode=0o700)
    repository = tool.no_links(repository) if published_fixture else generate_repository(output / 'synthetic-source')
    base = tool.git(repository, 'rev-parse', 'HEAD~2')
    tests = tool.git(repository, 'rev-parse', 'HEAD~1')
    target = tool.git(repository, 'rev-parse', 'HEAD')
    changed = tool.git(repository, 'diff', '--name-only', base, target).splitlines()
    if not changed or any(not name.startswith(FIXTURE) for name in changed):
        raise ValueError('A published rehearsal may change only the explicitly synthetic fixture path.')
    regression = output / 'regression.patch'
    repair = output / 'repair.patch'
    regression.write_bytes(tool.git(repository, 'diff', '--binary', base, tests, binary=True))
    repair.write_bytes(tool.git(repository, 'diff', '--binary', tests, target, binary=True))
    if published_fixture:
        # These are the actual saved synthetic SupportCase's safe export bytes,
        # committed with its regression tests. Never replace its identity/hash
        # with a newly generated CI case and call that an integrated workflow.
        manifest_path = tool.no_links(repository / FIXTURE / 'manifest.json')
        snapshot_path = tool.no_links(repository / FIXTURE / 'diagnostics.json')
        if any(not p.is_file() or p.stat().st_size > 131072 for p in (manifest_path, snapshot_path)):
            raise ValueError('Published fixture repair requires the saved case export JSON files.')
        manifest_bytes = manifest_path.read_bytes()
        raw = snapshot_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        snapshot = json.loads(raw)
        case_id = manifest.get('case_id')
    else:
        snapshot = {'format': 'isurvix-support-health-v1', 'release': base,
                    'scope': {'kind': 'platform', 'company_id': None, 'project_id': None},
                    'fixture': 'SYNTHETIC isolation rehearsal, not customer or site data'}
        raw = tool.canonical(snapshot)
        case_id = str(uuid.uuid4())
        manifest = {'format': 'isurvix-support-diagnostics-v1', 'case_id': case_id,
                    'report_sha256': hashlib.sha256(raw).hexdigest(), 'source_release': base}
        manifest_bytes = tool.canonical(manifest)
    bundle = output / 'diagnostics.zip'
    with ZipFile(bundle, 'x') as archive:
        archive.writestr('manifest.json', manifest_bytes)
        archive.writestr('diagnostics.json', raw)
    result = tool.prepare(repository=repository, output=output / 'prepared', bundle=bundle,
                          base_commit=base, tested_commit=target, regression_patch=regression,
                          repair_patch=repair, profile='synthetic-stdlib')
    # These are explicitly synthetic operational sentinels OUTSIDE every mount.
    private = output / 'not-mounted-synthetic-state'
    private.mkdir(mode=0o700)
    with closing(sqlite3.connect(private / 'original.sqlite3')) as database:
        with database:
            database.execute('create table retained (id integer primary key, answer text)')
            database.execute('insert into retained values (1, ?)', ('SYNTHETIC human answer: unchanged',))
    (private / 'original-photo.bin').write_bytes(b'SYNTHETIC original evidence bytes, never mounted')
    (output / 'sentinel-before.json').write_bytes(tool.canonical(tool.inventory(private)))
    (output / 'rehearsal.json').write_bytes(tool.canonical({
        'fixture_only': True, 'production_data_used': False, 'published_fixture': published_fixture,
        'base_commit': base, 'tested_commit': target, 'case_id': case_id,
        'report_sha256': manifest['report_sha256'], 'changed_paths': changed,
        'diagnostic_snapshot': snapshot, 'owner_release_approved': False}))
    return result


def run_rehearsal(repository, output, image, *, published_fixture=False):
    tool = operator()
    prepare_rehearsal(repository, output, published_fixture=published_fixture)
    saved = tool.run(Path(output) / 'prepared', image)
    before = tool.read_json(Path(output) / 'sentinel-before.json')
    after = tool.inventory(Path(output) / 'not-mounted-synthetic-state')
    if before != after:
        raise ValueError('The synthetic operational sentinel changed; no successful rehearsal proof is produced.')
    proof = {'fixture_only': True, 'production_data_used': False, 'real_docker_execution': True,
             'synthetic_originals_unchanged': True, 'sentinel_sha256': before,
             'tested_commit': saved['tested_commit'], 'published_fixture': published_fixture,
             'owner_release_approved': False, 'real_pr_created_by_this_tool': False}
    (Path(output) / 'verification.json').write_bytes(tool.canonical(proof))
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--published-fixture', action='store_true')
    args = parser.parse_args()
    try:
        result = run_rehearsal(args.repository, args.output, args.image, published_fixture=args.published_fixture)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
