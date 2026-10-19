param([string]$Model = 'qwen3.5:4b', [int]$Port = 11435)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot
$runtime = Join-Path $taskRoot '.local\runtime\ollama-0.40.5\ollama.exe'
$modelStore = Join-Path $taskRoot '.local\ollama\models'
if ($Port -lt 1024 -or $Port -gt 65535 -or $Port -eq 11434) { throw 'Choose a dedicated local photo AI port.' }
$photoUrl = "http://127.0.0.1:$Port"
$ready = $false
try { $null = Invoke-RestMethod "$photoUrl/api/tags" -TimeoutSec 2; $ready = $true } catch { }
if (-not $ready) {
    if (-not (Test-Path -LiteralPath $runtime) -or -not (Test-Path -LiteralPath $modelStore)) {
        throw 'The dedicated photo AI runtime and model store must be installed under .local first.'
    }
    if ((Get-AuthenticodeSignature -LiteralPath $runtime).Status -ne 'Valid') { throw 'The local photo AI executable signature is invalid.' }
    $taskNames = @('OLLAMA_HOST','OLLAMA_MODELS','OLLAMA_MAX_LOADED_MODELS','OLLAMA_NUM_PARALLEL','OLLAMA_KEEP_ALIVE','OLLAMA_NO_CLOUD','TEMP','TMP')
    $taskSaved = @{}
    foreach ($taskName in $taskNames) { $taskSaved[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process') }
    try {
        $env:OLLAMA_HOST = "127.0.0.1:$Port"
        $env:OLLAMA_MODELS = $modelStore
        $env:OLLAMA_MAX_LOADED_MODELS = '1'
        $env:OLLAMA_NUM_PARALLEL = '1'
        $env:OLLAMA_KEEP_ALIVE = '30m'
        $env:OLLAMA_NO_CLOUD = 'true'
        $env:TEMP = Join-Path $taskRoot '.local\tmp'
        $env:TMP = $env:TEMP
        New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
        $taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $taskProcess = Start-Process -FilePath $runtime -ArgumentList 'serve' -WorkingDirectory (Split-Path $runtime) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot ".local\photo-ai-$taskStamp.stdout.log") -RedirectStandardError (Join-Path $taskRoot ".local\photo-ai-$taskStamp.stderr.log") -PassThru
        $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskRoot '.local\photo-ai.pid')
    } finally {
        foreach ($taskName in $taskNames) { [Environment]::SetEnvironmentVariable($taskName, $taskSaved[$taskName], 'Process') }
    }
    for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
        Start-Sleep -Seconds 1
        try { $null = Invoke-RestMethod "$photoUrl/api/tags" -TimeoutSec 2; $ready = $true; break } catch { }
    }
}
if (-not $ready) { throw 'The dedicated photo AI service did not start. Check its .local logs.' }
$details = Invoke-RestMethod "$photoUrl/api/show" -Method Post -ContentType 'application/json' -Body (@{model=$Model} | ConvertTo-Json) -TimeoutSec 15
if (@($details.capabilities) -notcontains 'vision' -or $details.remote_host -or $details.remote_model) { throw 'The dedicated photo AI model must support local vision.' }
$env:ISURVIX_PHOTO_OLLAMA_URL = $photoUrl
Write-Host "Dedicated photo AI connected at $photoUrl. Local vision verified; GPU use is reported by Ollama after model load."
