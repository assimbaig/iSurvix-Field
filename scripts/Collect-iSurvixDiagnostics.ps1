param(
    [Parameter(Mandatory=$true)][string]$PhotoOllamaUrl,
    [string]$TextOllamaUrl = '',
    [string]$Model = 'qwen3.5:4b',
    [string]$PythonPath = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot '.local\venv\Scripts\python.exe' }
if (-not $TextOllamaUrl) { $TextOllamaUrl = $PhotoOllamaUrl }
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Use the existing project Python environment.' }
& $PythonPath (Join-Path $PSScriptRoot 'worker_runtime_tools.py') diagnostics --project-root $projectRoot --model $Model --photo-url $PhotoOllamaUrl --text-url $TextOllamaUrl --powershell-version $PSVersionTable.PSVersion.ToString()
if ($LASTEXITCODE -ne 0) { throw 'Private diagnostics could not be collected; no logs or credentials were uploaded.' }
