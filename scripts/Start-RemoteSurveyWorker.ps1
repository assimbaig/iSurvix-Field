param(
    [Parameter(Mandatory=$true)][string]$PhotoOllamaUrl,
    [string]$TextOllamaUrl = '',
    [string]$Model = 'qwen3.5:4b',
    [string]$ConfigPath = '',
    [string]$PythonPath = '',
    [switch]$CheckOnly,
    [switch]$Once
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot '.local\venv\Scripts\python.exe' }
if (-not $ConfigPath) { $ConfigPath = Join-Path $projectRoot '.local\private\remote-worker.json' }
if (-not $TextOllamaUrl) { $TextOllamaUrl = $PhotoOllamaUrl }
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Use the existing project Python environment.' }
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw 'Use the private configuration issued by the project Admin.' }
$runtimeTool = Join-Path $PSScriptRoot 'worker_runtime_tools.py'
& $PythonPath $runtimeTool check --model $Model --photo-url $PhotoOllamaUrl --text-url $TextOllamaUrl --config $ConfigPath
if ($LASTEXITCODE -ne 0) { throw 'Local installed-model metadata validation failed. No worker was started.' }
if ($CheckOnly) { return }
$names = @('ISURVIX_PHOTO_OLLAMA_URL','ISURVIX_OLLAMA_URL','ISURVIX_AI_MODEL')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    # These choices apply only to this worker process. Do not repoint or restart
    # any installed Ollama instance or change the user's global environment.
    $env:ISURVIX_PHOTO_OLLAMA_URL = $PhotoOllamaUrl
    $env:ISURVIX_OLLAMA_URL = $TextOllamaUrl
    $env:ISURVIX_AI_MODEL = $Model
    $arguments = @((Join-Path $projectRoot 'backend\manage.py'), 'remote_survey_worker',
        '--settings=checklist.settings_local', '--config', $ConfigPath)
    if ($Once) { $arguments += '--once' }
    & $PythonPath @arguments
    if ($LASTEXITCODE -ne 0) { throw 'The outbound worker stopped with an error. Saved server jobs and private checkpoints remain available.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
