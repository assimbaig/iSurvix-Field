function Test-LocalAIRuntime {
    param([string]$Model, [string]$ServiceUrl = 'http://127.0.0.1:11434')
    # Tags and capability metadata can succeed with a missing native runner.
    # A bounded generation request proves the installed runtime actually starts.
    try {
        $details = Invoke-RestMethod -Uri "$ServiceUrl/api/show" -Method Post -ContentType 'application/json' -Body (@{model=$Model} | ConvertTo-Json) -TimeoutSec 10
        if (@($details.capabilities) -notcontains 'vision' -or $details.remote_host -or $details.remote_model) { return $false }
        $payload = @{model=$Model;prompt='Reply OK.';stream=$false;think=$false;options=@{num_predict=8;num_ctx=2048;temperature=0}}
        $answer = Invoke-RestMethod -Uri "$ServiceUrl/api/generate" -Method Post -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 4) -TimeoutSec 90
        return ($answer.done -eq $true -and -not [string]::IsNullOrWhiteSpace([string]$answer.response))
    } catch { return $false }
}
