param([string]$Model = 'qwen3.5:4b', [int]$Port = 8000)
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
$env:ISURVIX_AI_MODEL = $Model
$env:ISURVIX_OLLAMA_URL = 'http://127.0.0.1:11434'
$aiReady = $false
try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3; $aiReady = $true } catch { }
if (-not $aiReady) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        Write-Host 'Starting Ollama on this PC...'
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        Start-Process -FilePath $ollamaCommand.Source -ArgumentList 'serve' -WindowStyle Minimized
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
    } else { Write-Host "Ollama is connected. Local model: $Model" }
} else { Write-Host 'Ollama is not responding. Start Ollama and use Check connection in the app.' }
& $venvPython (Join-Path $projectRoot 'scripts\local_setup.py')
if ($LASTEXITCODE -ne 0) { throw 'Local database setup did not finish. See the message above.' }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port $Port is already in use. Stop the previous app or run .\Start-iSurvix.ps1 -Port 8001" }
Write-Host "Open http://127.0.0.1:$Port/local/"
Write-Host 'Use your new local administrator credentials. Press Ctrl+C here to stop the app.'
Write-Host 'Your database, photos and secret are preserved in .local. Do not delete that folder.'
Start-Process "http://127.0.0.1:$Port/local/"
Push-Location (Join-Path $projectRoot 'backend')
try { & $venvPython manage.py runserver "127.0.0.1:$Port" --noreload } finally { Pop-Location }
