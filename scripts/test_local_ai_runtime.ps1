$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Test-LocalAIRuntime.ps1')
$script:runtimeCase = ''
$script:generationCalls = 0
function Invoke-RestMethod {
    param($Uri, $Method, $ContentType, $Body, $TimeoutSec)
    if ($Uri.EndsWith('/api/show')) {
        if ($script:runtimeCase -eq 'no-vision') { return @{capabilities=@('completion')} }
        if ($script:runtimeCase -eq 'remote') { return @{capabilities=@('vision');remote_host='https://example.invalid'} }
        return @{capabilities=@('vision','completion')}
    }
    if (-not $Uri.EndsWith('/api/generate')) { throw 'Unexpected endpoint' }
    $script:generationCalls++
    $request = $Body | ConvertFrom-Json
    if ($request.model -ne 'qwen3.5:4b' -or $request.stream -or $request.options.num_predict -gt 8) { throw 'Unbounded readiness request' }
    if ($script:runtimeCase -eq 'missing-runner') { throw 'Controlled HTTP 500 missing installed runner' }
    if ($script:runtimeCase -eq 'incomplete') { return @{done=$false;response=''} }
    return @{done=$true;response='OK'}
}
$cases = @(
    @{name='missing-runner';expected=$false;calls=1},
    @{name='no-vision';expected=$false;calls=0},
    @{name='remote';expected=$false;calls=0},
    @{name='incomplete';expected=$false;calls=1},
    @{name='ready';expected=$true;calls=1}
)
foreach ($case in $cases) {
    $script:runtimeCase=$case.name; $script:generationCalls=0
    $result=Test-LocalAIRuntime -Model 'qwen3.5:4b' -ServiceUrl 'http://127.0.0.1:11434'
    if ($result -ne $case.expected -or $script:generationCalls -ne $case.calls) { throw "Runtime readiness failed: $($case.name)" }
}
Write-Output 'PASS: 5 local AI runtime readiness cases; no native/network requests.'
