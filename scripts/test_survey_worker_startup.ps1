$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Start-SurveyWorkers.ps1')
$script:spawnedWorkers=@()
$script:workerHandles=@()
$script:closedWorkers=@()
$script:creationAttempts=0
$script:failAt=0
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    $script:creationAttempts++
    if ($script:creationAttempts -eq $script:failAt) { throw 'Controlled second consumer startup failure.' }
    $script:spawnedWorkers+=@{python=$FilePath;arguments=$ArgumentList;folder=$WorkingDirectory;style=$WindowStyle;stdout=$RedirectStandardOutput;stderr=$RedirectStandardError}
    $handle=[PSCustomObject]@{Id=$script:spawnedWorkers.Count;HasExited=$false}
    $script:workerHandles+=@($handle)
    return $handle
}
function taskkill.exe {
    param([Parameter(ValueFromRemainingArguments=$true)]$Arguments)
    $identifier=[int]$Arguments[1]
    $script:closedWorkers+=@($identifier)
    foreach ($handle in $script:workerHandles) { if ($handle.Id -eq $identifier) { $handle.HasExited=$true } }
}
$fixtureRoot=Join-Path ([System.IO.Path]::GetTempPath()) 'isurvix-synthetic-worker-test'
$python=Join-Path $fixtureRoot 'python.exe'
$workers=@(Start-iSurvixSurveyWorkers -PythonPath $python -ProjectRoot $fixtureRoot -RunStamp 'test-only')
if ($workers.Count -ne 2 -or $script:spawnedWorkers.Count -ne 2) { throw 'Two bounded survey consumers are required.' }
foreach ($worker in $script:spawnedWorkers) {
    if ($worker.python -ne $python -or $worker.style -ne 'Hidden' -or $worker.folder -ne (Join-Path $fixtureRoot 'backend')) { throw 'Invalid worker process scope.' }
    if (($worker.arguments -join ' ') -ne 'manage.py survey_processing_worker') { throw 'Use the existing durable worker.' }
}
if ($script:spawnedWorkers[0].stdout -eq $script:spawnedWorkers[1].stdout -or $script:spawnedWorkers[0].stderr -eq $script:spawnedWorkers[1].stderr) { throw 'Each worker must retain its own log.' }
foreach ($worker in $workers) { Stop-iSurvixWorkerTree $worker }
if ($script:closedWorkers.Count -ne 2) { throw 'Created handles must be individually cleaned.' }
$script:spawnedWorkers=@();$script:workerHandles=@();$script:closedWorkers=@();$script:creationAttempts=0;$script:failAt=2
$caught=$false
try { $null=@(Start-iSurvixSurveyWorkers -PythonPath $python -ProjectRoot $fixtureRoot -RunStamp 'controlled-failure') } catch { $caught=$true }
if (-not $caught -or $script:workerHandles.Count -ne 1 -or $script:closedWorkers.Count -ne 1 -or -not $script:workerHandles[0].HasExited) { throw 'A partial consumer launch must clean up its acquired handle before raising.' }
Write-Output 'PASS: bounded consumers, distinct logs, hidden windows and partial-start cleanup; no real processes launched.'
