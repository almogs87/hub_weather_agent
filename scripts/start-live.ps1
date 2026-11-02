param(
    [ValidateSet('groq','openai')][string]$Provider = 'groq',
    [string]$Model = '',
    [ValidateSet('serve','evaluate')][string]$Action = 'serve'
)
$ErrorActionPreference = 'Stop'
if (-not $Model) {
    if ($Provider -eq 'groq') { $Model = 'openai/gpt-oss-20b' }
    else { throw 'Specify -Model for OpenAI.' }
}
$keyVariable = if ($Provider -eq 'groq') { 'GROQ_API_KEY' } else { 'OPENAI_API_KEY' }
$previousKey = [Environment]::GetEnvironmentVariable($keyVariable, 'Process')
$previousProvider = $env:LLM_PROVIDER
$previousModel = $env:LLM_MODEL
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not $previousKey) {
        $secureKey = Read-Host "Enter your $Provider API key (hidden; never saved to a file)" -AsSecureString
        $credential = [System.Management.Automation.PSCredential]::new('api', $secureKey)
        [Environment]::SetEnvironmentVariable($keyVariable, $credential.GetNetworkCredential().Password, 'Process')
    }
    $env:LLM_PROVIDER = $Provider
    $env:LLM_MODEL = $Model
    Write-Host "Provider: $Provider | Model: $Model"
    if ($Action -eq 'evaluate') {
        & python -m evals.run --live-model --report "eval-results/$Provider-$($Model.Replace('/','-')).json"
    } else {
        & python -m app.server
    }
    if ($LASTEXITCODE -ne 0) { throw "Application exited with code $LASTEXITCODE" }
} finally {
    [Environment]::SetEnvironmentVariable($keyVariable, $previousKey, 'Process')
    $env:LLM_PROVIDER = $previousProvider
    $env:LLM_MODEL = $previousModel
    if ($secureKey) { $secureKey.Dispose() }
    $credential = $null
    Pop-Location
}
