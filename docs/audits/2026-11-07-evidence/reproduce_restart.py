import ast, json, sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

source = Path(sys.argv[1] if len(sys.argv) > 1 else 'deploy/hostinger/controller.py').read_text()
tree = ast.parse(source)
engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Engine')
method = next(n for n in engine.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))

class ExistingPath:
    def __truediv__(self, name): return self
    def exists(self): return True

results = []
for phase in ('public_opening', 'failure_recorded'):
    saved = {'phase': phase, 'failure_phase': 'public_opening'}
    calls = []
    namespace = {'nullcontext': nullcontext, 'lock': lambda p: nullcontext(),
                 'read_env': lambda p: {},
                 'consumer': SimpleNamespace(_json=lambda p: saved),
                 'DeliveryError': ValueError, 'sqlite3': __import__('sqlite3')}
    exec(compile(module, '<actual Engine.run from 17a699a>', 'exec'), namespace)
    def rollback(state):
        calls.append('rollback')
        return {'status': 'rolled_back'}
    def freeze(state):
        calls.append('freeze')
        return {'status': 'operator_recovery_required'}
    fake = SimpleNamespace(root=ExistingPath(), environment=ExistingPath(),
                           rollback=rollback, freeze=freeze,
                           result=lambda state, status: {'status': status})
    outcome = namespace['run'](fake, {})
    results.append({'journal_phase': phase, 'failure_phase': 'public_opening',
                    'recovery_calls': calls, 'outcome': outcome})
assert results[0]['recovery_calls'] == ['freeze']
assert results[1]['recovery_calls'] == ['rollback']
print(json.dumps({'source': '17a699a98a9925b1095172b787af7ebedbd60919',
                  'method': 'actual AST-extracted Engine.run',
                  'scope': 'synthetic recovery dispatch only; no operational data or host calls',
                  'results': results}, indent=2))
