# Independent staging ingress configuration review — 31 October 2026

No new exploitable finding was established in the narrow ingress repair. Independent execution passed all 20 existing deployment tests in 19.142 seconds, zero failures/errors/skips, exit 0. The ordinary runner reported zero external network attempts and zero HTTP fixture connections. This review does not establish actual Linux or target deployment acceptance.

## Scope and evidence

Reviewed commit `7e88049e0640d15f353f1ab209d48687409ff091`, limited to its changes in `deploy/compose.yaml`, `deploy/verify_staging.sh`, and `backend/core/test_staging_deployment.py`. Read their complete current contents and commit diff after the functional GREEN/freeze signal. The reviewer followed the installed Agency AppSec definition and repository owner rules documented in the separate WAL review. No implementation source or tests were changed.

The authorized functional change adds a noninternal bridge only to the proxy while retaining its existing internal application network. Source review confirms:

- The web service remains attached solely to the internal application network. It has no published host ports. SQLite and media remain on the web service's persistent `/data` mount.
- Only the proxy publishes ports, both bound explicitly to host `127.0.0.1` (8080 and 8443). The new ingress network does not attach to web or publish its port 8000.
- Proxy mounts remain read-only Nginx configuration, static output, and TLS files. No database, private media, or Django secret is mounted into proxy. The web-only file secret, nonroot identities, dropped capabilities, read-only root filesystems and no-new-privileges options are unchanged.
- The helper now requires `compose port proxy 8443` to equal `127.0.0.1:8443` before its existing TLS readiness/static/media-denial probes. A missing/misbound port fails the rehearsal. TLS probes still use the expected certificate with `--cacert` and the bound fixture hostname; no insecure certificate bypass was added.
- No backup logic, data permissions, migration behavior, model service, approval policy or existing security finding is changed by this commit.

The new existing graph regression asserts that published services have a noninternal network, only proxy is published, every publication binds loopback, and web remains exclusively internal. The full 20-test module also exercises the existing private-media policy, immutable image references, secret/configuration rejection, preservation fixtures, and privileged read-only host-validation helper. That helper test substitutes a local command double and performs no sudo/deployment.

Independent command from `.local/b4`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_staging_deployment --verbosity 2
```

Private raw receipt: `.local/cloud-staging-20261031/wal-review/configuration-tests.log`. All fixtures stayed under this F: worktree. SHA256 before and after execution matched:

| File | SHA256 |
| --- | --- |
| `deploy/compose.yaml` | `f8b568ed5886262b05189ab05cc921c66afc7fff3a75cad6285a66b9c2bd14eb` |
| `deploy/verify_staging.sh` | `8aba4e550041108a3b919470f0a936ad402cc81af9db88be312b29b9c90afb34` |
| `backend/core/test_staging_deployment.py` | `d13a9005d0297277164e9ca27fb9cef16cbd74c3e4277a3290e03a28c4aae779` |

## Findings, recommendations and limits

No new finding severity is assigned because no new exploitable finding was established in this scoped review. Recommendation: retain the network-boundary regression and require the actual disposable Linux TLS readiness/media-denial probes to pass before claiming the ingress repair works at runtime.

The noninternal ingress bridge intentionally gives the proxy normal bridge connectivity; this is not proof of an outbound network deny policy or isolation against a compromised host/proxy. Host loopback publication is not equivalent to access control against other host processes or containers already able to reach the proxy network. Those wider threat-model questions were not tested here.

The reviewer did not execute Docker/Compose, the rehearsal script, external requests, cloud deployment, native AI, actual proxy HTTP checks, or the Linux CI run. Root owns the separate actual Linux runtime evidence. Existing D1/D2/CS1/CS2 remain unapproved and unfixed. No findings were remediated, operational services/data altered, credentials inspected, source changes made, or commits created by this reviewer.
