function Start-iSurvixSurveyWorkers {
    param([string]$PythonPath, [string]$ProjectRoot, [string]$RunStamp)
    # One consumer may complete cache-only work while the other uses the GPU.
    # Actual image inference remains protected by the existing shared GPU lease.
    foreach ($lane in @('main','reuse')) {
        Start-Process -FilePath $PythonPath -ArgumentList @('manage.py','survey_processing_worker') -WorkingDirectory (Join-Path $ProjectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot ".local\survey-processing-$lane-$RunStamp.stdout.log") -RedirectStandardError (Join-Path $ProjectRoot ".local\survey-processing-$lane-$RunStamp.stderr.log") -PassThru
    }
}
