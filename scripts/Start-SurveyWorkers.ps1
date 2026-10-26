function Stop-iSurvixWorkerTree {
    param($WorkerProcess)
    if (-not $WorkerProcess) { return }
    try {
        if (-not $WorkerProcess.HasExited) {
            # Stop only the process returned by this launch, including its
            # virtual-environment runtime child. Never kill by process name.
            & taskkill.exe /PID $WorkerProcess.Id /T /F | Out-Null
        }
    } catch {
        Write-Warning "Worker $($WorkerProcess.Id) cleanup could not be confirmed."
    }
}

function Start-iSurvixSurveyWorkers {
    param([string]$PythonPath, [string]$ProjectRoot, [string]$RunStamp)
    # One consumer may complete cache-only work while the other uses the GPU.
    # Actual image inference remains protected by the existing shared GPU lease.
    $started = New-Object 'System.Collections.Generic.List[object]'
    try {
        foreach ($lane in @('main','reuse')) {
            $workerProcess = Start-Process -FilePath $PythonPath -ArgumentList @('manage.py','survey_processing_worker') -WorkingDirectory (Join-Path $ProjectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot ".local\survey-processing-$lane-$RunStamp.stdout.log") -RedirectStandardError (Join-Path $ProjectRoot ".local\survey-processing-$lane-$RunStamp.stderr.log") -PassThru
            $started.Add($workerProcess)
        }
    } catch {
        # A failed second launch must not strand the first handle inside a
        # command whose assignment never completed in its caller.
        foreach ($workerProcess in $started) { Stop-iSurvixWorkerTree $workerProcess }
        throw
    }
    return $started.ToArray()
}

function Invoke-iSurvixWorkerSession {
    param([string]$PythonPath, [string]$ProjectRoot, [string]$RunStamp, [int]$Port)
    $started = New-Object 'System.Collections.Generic.List[object]'
    $locationPushed = $false
    try {
        $workerProcess = Start-Process -FilePath $PythonPath -ArgumentList @('manage.py','photo_worker') -WorkingDirectory (Join-Path $ProjectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot ".local\worker-$RunStamp.stdout.log") -RedirectStandardError (Join-Path $ProjectRoot ".local\worker-$RunStamp.stderr.log") -PassThru
        $started.Add($workerProcess)
        $workerProcess = Start-Process -FilePath $PythonPath -ArgumentList @('manage.py','photo_search_worker') -WorkingDirectory (Join-Path $ProjectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot ".local\photo-search-$RunStamp.stdout.log") -RedirectStandardError (Join-Path $ProjectRoot ".local\photo-search-$RunStamp.stderr.log") -PassThru
        $started.Add($workerProcess)
        $surveyWorkers = @(Start-iSurvixSurveyWorkers -PythonPath $PythonPath -ProjectRoot $ProjectRoot -RunStamp $RunStamp)
        foreach ($workerProcess in $surveyWorkers) { $started.Add($workerProcess) }
        Write-Host 'The independent photo pipeline is running. Saved stages survive restart; human confirmation remains required.'
        Push-Location (Join-Path $ProjectRoot 'backend')
        $locationPushed = $true
        & $PythonPath manage.py runserver "127.0.0.1:$Port" --noreload
        if ($LASTEXITCODE -ne 0) { throw "The local application exited with code $LASTEXITCODE." }
    } finally {
        if ($locationPushed) { Pop-Location }
        foreach ($workerProcess in $started) { Stop-iSurvixWorkerTree $workerProcess }
    }
}
