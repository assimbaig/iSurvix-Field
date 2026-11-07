"""CI-only post-activation checks, separate from the strict production gate.

The trusted updater already proved empty additive tables before activation. A
real login then legitimately records the installed release. Validate exactly
those expected runtime rows and use a disposable comparison COPY to rerun the
unchanged migration verifier. Never edit a customer/runtime database to pass CI.
"""
import ast
from contextlib import closing
from datetime import date,datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile


def _proof():
    spec=importlib.util.spec_from_file_location('reviewed_rehearsal_migration_proof',Path(__file__).with_name('upgrade_fixture.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_release_notes(path):
    """Read pinned package metadata as data: never import/exec candidate Python."""
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:raise ValueError('Bounded release-note metadata is required.')
    try:
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        assignments=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='NOTES' for target in node.targets)]
        if len(assignments)!=1 or not isinstance(assignments[0].value,ast.Dict):raise ValueError()
        required={'version','title','date','changes'};values={}
        for key,value in zip(assignments[0].value.keys,assignments[0].value.values):
            name=ast.literal_eval(key)
            if name in required:
                if name in values:raise ValueError()
                values[name]=ast.literal_eval(value)
        if set(values)!=required or not isinstance(values['version'],str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})(?:\.(?:0|[1-9][0-9]{0,3}))?',values['version']):raise ValueError()
        if not isinstance(values['title'],str) or not 1<=len(values['title'])<=180:raise ValueError()
        if not isinstance(values['date'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',values['date']):raise ValueError()
        date.fromisoformat(values['date'])
        if not isinstance(values['changes'],(list,tuple)) or not 1<=len(values['changes'])<=100 or any(not isinstance(item,str) or not 1<=len(item)<=1000 for item in values['changes']):raise ValueError()
        values['changes']=list(values['changes']);return values
    except (SyntaxError,ValueError,TypeError,KeyError,RecursionError):raise ValueError('Release notes must contain explicit, non-executable reviewed metadata.') from None


def verify_post_activation(before,database,*,source_database,preactivation_before,preactivation_proof,expected_release,expected_notes,scratch_directory):
    if os.environ.get('ISURVIX_DISPOSABLE_REHEARSAL')!='yes':raise ValueError('Post-activation normalization is limited to the explicit disposable rehearsal.')
    if not re.fullmatch('[0-9a-f]{40}',expected_release):raise ValueError('An exact immutable target release is required.')
    proof=_proof()
    # The caller first verifies the signed terminal replay and binds these exact
    # files to its retention artifacts. This additional check binds their content
    # to the immutable source backup rather than accepting a success description.
    if proof.snapshot(source_database)!=preactivation_before:raise ValueError('Preactivation source snapshot differs from its verified backup.')
    canonical=json.dumps(preactivation_before,sort_keys=True,separators=(',',':')).encode()
    if (preactivation_proof.get('retained_rows_sha256')!=hashlib.sha256(canonical).hexdigest()
            or preactivation_proof.get('retained_rows')!=sum(len(table['rows']) for table in preactivation_before.values())
            or preactivation_proof.get('retained_tables')!=len(preactivation_before)):
        raise ValueError('Preactivation retained-row proof is missing or belongs to another snapshot.')
    after=proof.snapshot(database)
    def named(table):
        value=after.get(table)
        if not value:raise ValueError('Runtime verification table is missing.')
        return [dict(zip(value['columns'],row)) for row in value['rows']]
    additions={};normalize=[]
    table='core_installedrelease'
    if table not in before:
        history=named(table)
        if len(history)!=1:raise ValueError('The two rehearsal logins must create exactly one installed-release record.')
        row=history[0]
        try:changes=json.loads(row['changes']);datetime.fromisoformat(row['first_seen_at'])
        except (ValueError,TypeError,KeyError):raise ValueError('Runtime release history metadata is invalid.') from None
        if (type(row.get('id')) is not int or row['id']<=0 or row.get('release_key')!=expected_release
                or row.get('version')!=expected_notes['version'] or row.get('title')!=expected_notes['title']
                or row.get('release_date')!=expected_notes['date'] or changes!=list(expected_notes['changes'])):
            raise ValueError('Runtime installed-release notes differ from the exact checked package.')
        additions[table]=1;normalize.append(table)
    table='core_dataexportworkerlease'
    if table not in before:
        leases=named(table)
        if after.get('core_dataexportjob',{}).get('rows'):raise ValueError('The customer login rehearsal must not create export jobs.')
        if leases and leases!=[{'key':'data-exports','token':None,'expires_at':None}]:raise ValueError('Only the known idle export-worker singleton is permitted after quiescence.')
        additions[table]=len(leases)
        if leases:normalize.append(table)
    # No other new-table rows are normalized. The unchanged strict verifier below
    # rejects recovery requests/throttles/export jobs, schema changes and old-row
    # corruption exactly as it does before public activation.
    scratch=Path(scratch_directory)
    if scratch.is_symlink() or not scratch.is_dir():raise ValueError('Use an existing disposable comparison directory.')
    with tempfile.TemporaryDirectory(prefix='post-activation-compare-',dir=scratch) as temporary:
        comparison=Path(temporary)/'comparison.sqlite3'
        with closing(sqlite3.connect(Path(database).absolute().as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(comparison)) as target:
            source.backup(target)
            with target:
                for name in normalize:target.execute('DELETE FROM '+proof._identifier(name))
        result=proof.assert_retained(before,comparison,source_database=source_database)
    return {**result,'phase':'post-activation','runtime_additions':additions,'migration_pre_activation':preactivation_proof}
