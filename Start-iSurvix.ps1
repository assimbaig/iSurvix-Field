param([string]$Model = 'qwen3.5:4b', [int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Choose a port between 1024 and 65535.' }
$venvPython = Join-Path $projectRoot '.local\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 for Windows with the Python launcher, then run this file again.' }
    & py -3.12 -c 'import sys; print(sys.version.split()[0])'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Install it from python.org, then try again.' }
    & py -3.12 -m venv (Join-Path $projectRoot '.local\venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}
$requirementsPath = Join-Path $projectRoot 'backend\requirements.txt'
$stampPath = Join-Path $projectRoot '.local\requirements.sha256'
$requirementsHash = (Get-FileHash -LiteralPath $requirementsPath -Algorithm SHA256).Hash
$previousHash = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
if ($previousHash -ne $requirementsHash) {
    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the message above and your internet connection.' }
    Set-Content -LiteralPath $stampPath -Value $requirementsHash
}
$env:DJANGO_SETTINGS_MODULE = 'checklist.settings_local'
$runtimeTemp = Join-Path $projectRoot '.local\tmp'
New-Item -ItemType Directory -Force -Path $runtimeTemp | Out-Null
$env:TEMP = $runtimeTemp
$env:TMP = $runtimeTemp
$env:ISURVIX_AI_MODEL = $Model
$env:ISURVIX_OLLAMA_URL = 'http://127.0.0.1:11434'
$aiReady = $false
$existingVisionReady = $false
try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3; $aiReady = $true } catch { }
if (-not $aiReady) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        Write-Host 'Starting Ollama on this PC...'
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        Start-Process -FilePath $ollamaCommand.Source -ArgumentList 'serve' -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 10; $attempt++) {
            Start-Sleep -Seconds 1
            try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $aiReady = $true; break } catch { }
        }
    }
}
if ($aiReady) {
    $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    if (@($tags.models.name) -notcontains $Model) {
        Write-Host "Ollama is running, but $Model is not installed."
        Write-Host "In another PowerShell window, run: ollama pull $Model"
        Write-Host 'The survey app can start while the model is downloading.'
    } else {
        Write-Host "Ollama is connected. Local model: $Model"
        try {
            $details = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/show' -Method Post -ContentType 'application/json' -Body (@{ model = $Model } | ConvertTo-Json) -TimeoutSec 10
            if (@($details.capabilities) -contains 'vision' -and -not $details.remote_host -and -not $details.remote_model) {
                . (Join-Path $projectRoot 'scripts\Test-LocalAIRuntime.ps1')
                $existingVisionReady = Test-LocalAIRuntime -Model $Model -ServiceUrl $env:ISURVIX_OLLAMA_URL
                if ($existingVisionReady) {
                    Write-Host 'Local vision metadata and a bounded generation request succeeded. The worker rechecks actual image processing.'
                } else {
                    Write-Host 'Ollama metadata responds, but local generation failed. Checking the existing project photo AI runtime.'
                }
            } else { Write-Host 'This model does not report local vision support. Photo analysis will remain blocked.' }
        } catch { Write-Host 'Vision capability could not be verified. The photo worker will require verification before analysis.' }
    }
} else { Write-Host 'Ollama is not responding. Start Ollama and use Check connection in the app.' }
try {
    if ($existingVisionReady) {
        # Reuse the installed service instead of switching model stores on each
        # GUI launch. Saved inference identities remain subject to worker checks.
        $env:ISURVIX_PHOTO_OLLAMA_URL = $env:ISURVIX_OLLAMA_URL
        Write-Host "Text and photo AI use the existing local service at $env:ISURVIX_OLLAMA_URL."
    } else {
        & (Join-Path $projectRoot 'scripts\Start-PhotoAI.ps1') -Model $Model
        $env:ISURVIX_OLLAMA_URL = $env:ISURVIX_PHOTO_OLLAMA_URL
    }
} catch {
    $env:ISURVIX_PHOTO_OLLAMA_URL = $env:ISURVIX_OLLAMA_URL
    Write-Host "Dedicated photo AI unavailable: $($_.Exception.Message) Using the existing local AI queue."
}
& $venvPython (Join-Path $projectRoot 'scripts\local_setup.py') --browser-admin
if ($LASTEXITCODE -ne 0) { throw 'Local database setup did not finish. See the message above.' }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port $Port is already in use. Stop the previous app or run .\Start-iSurvix.ps1 -Port 8001" }
Write-Host "Open http://127.0.0.1:$Port/local/"
Write-Host 'Use your new local administrator credentials. Press Ctrl+C here to stop the app.'
Write-Host 'Your database, photos and secret are preserved in .local. Do not delete that folder.'
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port/local/" }
$runStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$worker = Start-Process -FilePath $venvPython -ArgumentList @('manage.py', 'photo_worker') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot ".local\worker-$runStamp.stdout.log") -RedirectStandardError (Join-Path $projectRoot ".local\worker-$runStamp.stderr.log") -PassThru
$searchWorker = Start-Process -FilePath $venvPython -ArgumentList @('manage.py', 'photo_search_worker') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot ".local\photo-search-$runStamp.stdout.log") -RedirectStandardError (Join-Path $projectRoot ".local\photo-search-$runStamp.stderr.log") -PassThru
. (Join-Path $projectRoot 'scripts\Start-SurveyWorkers.ps1')
$surveyWorkers = @(Start-iSurvixSurveyWorkers -PythonPath $venvPython -ProjectRoot $projectRoot -RunStamp $runStamp)
Write-Host 'The independent photo pipeline is running: image analysis, checklist comparison, then human confirmation. Durable stages survive restart.'
Push-Location (Join-Path $projectRoot 'backend')
try { & $venvPython manage.py runserver "127.0.0.1:$Port" --noreload } finally {
    Pop-Location
    # Windows virtual-environment Python can spawn a runtime child; stop that
    # exact worker tree so it cannot remain detached after the launcher exits.
    if ($worker -and -not $worker.HasExited) { & taskkill.exe /PID $worker.Id /T /F | Out-Null }
    if ($searchWorker -and -not $searchWorker.HasExited) { & taskkill.exe /PID $searchWorker.Id /T /F | Out-Null }
    foreach ($surveyWorker in $surveyWorkers) {
        if ($surveyWorker -and -not $surveyWorker.HasExited) { & taskkill.exe /PID $surveyWorker.Id /T /F | Out-Null }
    }
}
