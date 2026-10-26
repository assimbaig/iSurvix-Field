"""Execute the PowerShell lifecycle with disposable mocked worker handles.

The same logic runs under Windows PowerShell or an explicitly selected portable
pwsh. Actual Windows process-tree termination is verified separately on Windows.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import skipUnless

from django.test import SimpleTestCase


POWERSHELL = (os.environ.get('ISURVIX_TEST_POWERSHELL') or
    shutil.which('powershell.exe') or shutil.which('pwsh'))
ROOT = Path(__file__).resolve().parents[2]
PROBE = r'''
param([string]$Helper,[string]$FixtureRoot,[string]$Mode)
$ErrorActionPreference='Stop'
. $Helper
$script:attempts=0;$script:created=@();$script:killed=@();$script:appCalls=0
$script:failAt=switch($Mode){'first-failure'{1};'second-failure'{2};'session-search-failure'{2};'session-survey-failure'{4};default{0}}
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    $script:attempts++
    if($script:attempts -eq $script:failAt){throw 'Controlled worker creation failure'}
    $process=[PSCustomObject]@{Id=(100+$script:created.Count);HasExited=$false}
    $script:created+=@($process)
    return $process
}
function taskkill.exe {
    param([Parameter(ValueFromRemainingArguments=$true)]$Arguments)
    $identifier=[int]$Arguments[1]
    $script:killed+=@($identifier)
    foreach($process in $script:created){if($process.Id -eq $identifier){$process.HasExited=$true}}
}
function Invoke-SyntheticPython {
    $script:appCalls++
    if($Mode -eq 'app-failure'){throw 'Controlled application startup failure'}
    $global:LASTEXITCODE=if($Mode -eq 'app-nonzero'){17}else{0}
}
$caught=$false
try{
    if($Mode -in @('first-failure','second-failure')){
        $workers=@(Start-iSurvixSurveyWorkers -PythonPath 'Invoke-SyntheticPython' -ProjectRoot $FixtureRoot -RunStamp 'controlled')
    }else{
        Invoke-iSurvixWorkerSession -PythonPath 'Invoke-SyntheticPython' -ProjectRoot $FixtureRoot -RunStamp 'controlled' -Port 18000
    }
}catch{$caught=$true}
if($Mode -ne 'success' -and -not $caught){throw 'The controlled startup failure was swallowed.'}
if($Mode -eq 'success' -and $caught){throw 'The successful worker session failed.'}
$expectedAttempts=switch($Mode){'first-failure'{1};'second-failure'{2};'session-search-failure'{2};default{4}}
if($script:attempts -ne $expectedAttempts){throw 'The intended worker acquisition boundary was not reached.'}
$expected=@($script:created|ForEach-Object{$_.Id}|Sort-Object)
$actual=@($script:killed|Sort-Object)
if(($expected -join ',') -ne ($actual -join ',')){throw "Created worker handles escaped cleanup: expected=$($expected -join ',');actual=$($actual -join ',')"}
if(@($script:created|Where-Object{-not $_.HasExited}).Count){throw 'A worker remains alive after session cleanup.'}
if($Mode -in @('success','app-failure','app-nonzero') -and $script:appCalls -ne 1){throw 'The application must be invoked once inside the owned worker session.'}
@{mode=$Mode;created=$script:created.Count;cleaned=$script:killed.Count;app_calls=$script:appCalls;controlled_failure=$caught}|ConvertTo-Json -Compress
'''


@skipUnless(POWERSHELL, 'PowerShell lifecycle checks require powershell.exe or pwsh.')
class WorkerLifecycleTests(SimpleTestCase):
    def probe(self, mode):
        with tempfile.TemporaryDirectory(prefix='isurvix-worker-lifecycle-') as temporary:
            directory = Path(temporary)
            (directory / 'backend').mkdir()
            script = directory / 'probe.ps1'
            script.write_text(PROBE, encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive',
                '-ExecutionPolicy', 'Bypass', '-File', str(script),
                '-Helper', str(ROOT / 'scripts' / 'Start-SurveyWorkers.ps1'),
                '-FixtureRoot', str(directory), '-Mode', mode],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_worker_failure_creates_no_orphan(self):
        self.probe('first-failure')

    def test_second_worker_failure_cleans_the_first_created_worker(self):
        self.probe('second-failure')

    def test_search_worker_failure_cleans_the_photo_worker(self):
        self.probe('session-search-failure')

    def test_partial_survey_launch_cleans_itself_and_prior_workers(self):
        self.probe('session-survey-failure')

    def test_application_startup_exception_cleans_every_created_worker(self):
        self.probe('app-failure')

    def test_application_nonzero_exit_cleans_every_created_worker(self):
        self.probe('app-nonzero')

    def test_normal_application_shutdown_cleans_every_created_worker(self):
        self.probe('success')


@skipUnless(os.name == 'nt' and shutil.which('powershell.exe'),
    'Native Windows process-tree validation requires Windows PowerShell.')
class WindowsProcessTreeTests(SimpleTestCase):
    def test_owned_parent_and_child_stop_while_an_unrelated_process_survives(self):
        owner_source = r'''
param([string]$ChildPidPath)
$child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-Command','Start-Sleep -Seconds 60') -WindowStyle Hidden -PassThru
$child.Id|Set-Content -LiteralPath $ChildPidPath
Start-Sleep -Seconds 60
'''
        probe_source = r'''
param([string]$Helper,[string]$OwnerScript,[string]$ChildPidPath)
$ErrorActionPreference='Stop'
. $Helper
$owner=$null;$unrelated=$null;$childIdentifier=$null
try{
    $unrelated=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-Command','Start-Sleep -Seconds 60') -WindowStyle Hidden -PassThru
    $owner=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-File',('"{0}"' -f $OwnerScript),'-ChildPidPath',('"{0}"' -f $ChildPidPath)) -WindowStyle Hidden -PassThru
    for($attempt=0;$attempt -lt 50 -and -not (Test-Path -LiteralPath $ChildPidPath);$attempt++){Start-Sleep -Milliseconds 100}
    if(-not (Test-Path -LiteralPath $ChildPidPath)){throw 'The isolated child did not start.'}
    $childIdentifier=[int](Get-Content -LiteralPath $ChildPidPath -Raw)
    Stop-iSurvixWorkerTree $owner
    for($attempt=0;$attempt -lt 20 -and ((Get-Process -Id $owner.Id -ErrorAction SilentlyContinue) -or (Get-Process -Id $childIdentifier -ErrorAction SilentlyContinue));$attempt++){Start-Sleep -Milliseconds 100}
    if((Get-Process -Id $owner.Id -ErrorAction SilentlyContinue) -or (Get-Process -Id $childIdentifier -ErrorAction SilentlyContinue)){throw 'The owned worker tree remains alive.'}
    $unrelated.Refresh()
    if($unrelated.HasExited){throw 'Cleanup stopped an unrelated process.'}
}finally{
    # Every ID below was created by this isolated test. Clean up even when the
    # product regression fails, without relying on the product cleanup helper.
    foreach($identifier in @($childIdentifier,$owner.Id,$unrelated.Id)){
        if($identifier){try{& taskkill.exe /PID $identifier /T /F 2>$null|Out-Null}catch{}}
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='isurvix-windows-tree-') as temporary:
            directory = Path(temporary)
            owner, probe = directory / 'owner.ps1', directory / 'probe.ps1'
            owner.write_text(owner_source, encoding='utf-8')
            probe.write_text(probe_source, encoding='utf-8')
            result = subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-NonInteractive',
                '-ExecutionPolicy', 'Bypass', '-File', str(probe),
                '-Helper', str(ROOT / 'scripts' / 'Start-SurveyWorkers.ps1'),
                '-OwnerScript', str(owner), '-ChildPidPath', str(directory / 'child.pid')],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
