$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Start-SurveyWorkers.ps1')
$script:spawnedWorkers=@()
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    $script:spawnedWorkers+=@{python=$FilePath;arguments=$ArgumentList;folder=$WorkingDirectory;style=$WindowStyle;stdout=$RedirectStandardOutput;stderr=$RedirectStandardError}
    return [PSCustomObject]@{Id=$script:spawnedWorkers.Count;HasExited=$false}
}
$workers=@(Start-iSurvixSurveyWorkers -PythonPath 'F:\Synthetic\python.exe' -ProjectRoot 'F:\Synthetic' -RunStamp 'test-only')
if ($workers.Count -ne 2 -or $script:spawnedWorkers.Count -ne 2) { throw 'Two bounded survey consumers are required.' }
foreach ($worker in $script:spawnedWorkers) {
    if ($worker.python -ne 'F:\Synthetic\python.exe' -or $worker.style -ne 'Hidden' -or $worker.folder -ne 'F:\Synthetic\backend') { throw 'Invalid worker process scope.' }
    if (($worker.arguments -join ' ') -ne 'manage.py survey_processing_worker') { throw 'Use the existing durable worker.' }
}
if ($script:spawnedWorkers[0].stdout -eq $script:spawnedWorkers[1].stdout -or $script:spawnedWorkers[0].stderr -eq $script:spawnedWorkers[1].stderr) { throw 'Each worker must retain its own log.' }
Write-Output 'PASS: two bounded existing survey workers with distinct logs and hidden windows; no processes launched.'
