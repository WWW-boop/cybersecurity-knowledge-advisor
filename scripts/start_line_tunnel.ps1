#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$cloudflared = Join-Path $projectRoot ".tools\cloudflared\cloudflared.exe"
$envFile = Join-Path $projectRoot ".env"
$issues = [System.Collections.Generic.List[string]]::new()

function Get-EnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        return $null
    }
    $escapedName = [regex]::Escape($Name)
    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^\s*$escapedName\s*=" } |
        Select-Object -First 1
    if ($null -eq $line) {
        return $null
    }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value.Length -ge 2) {
        $quoted =
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        if ($quoted) {
            $value = $value.Substring(1, $value.Length - 2)
        }
    }
    return $value
}

if (-not (Test-Path -LiteralPath $cloudflared -PathType Leaf)) {
    $issues.Add("cloudflared is missing; run .\scripts\install_cloudflared.ps1")
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    $issues.Add(".env is missing")
} else {
    foreach ($name in @("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN", "NEO4J_PASSWORD")) {
        if ([string]::IsNullOrWhiteSpace((Get-EnvValue $name))) {
            $issues.Add("$name is empty in .env")
        }
    }
    $jevKey = Get-EnvValue "JEV_API_KEY"
    $legacyJevKey = Get-EnvValue "TYPE_SAFE"
    if ([string]::IsNullOrWhiteSpace($jevKey) -and [string]::IsNullOrWhiteSpace($legacyJevKey)) {
        $issues.Add("JEV_API_KEY (or TYPE_SAFE) is empty in .env")
    }

    $provider = Get-EnvValue "LINE_PROVIDER"
    if ([string]::IsNullOrWhiteSpace($provider)) {
        $provider = "openai"
    }
    switch ($provider.ToLowerInvariant()) {
        "openai" {
            if ([string]::IsNullOrWhiteSpace((Get-EnvValue "PSU_AI_API_KEY"))) {
                $issues.Add("PSU_AI_API_KEY is empty while LINE_PROVIDER=openai")
            }
        }
        "ollama" {
            if ([string]::IsNullOrWhiteSpace((Get-EnvValue "OLLAMA_MODEL"))) {
                $issues.Add("OLLAMA_MODEL is empty while LINE_PROVIDER=ollama")
            }
        }
        default {
            $issues.Add("LINE_PROVIDER must be openai or ollama")
        }
    }
}

$healthUrl = "http://127.0.0.1:$Port/health"
try {
    $null = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
} catch {
    $issues.Add("API is not reachable at $healthUrl")
}

if ($CheckOnly) {
    if ($issues.Count -eq 0) {
        Write-Host "READY=true"
    } else {
        Write-Host "READY=false"
        foreach ($issue in $issues) {
            Write-Host "- $issue"
        }
    }
    exit 0
}

if ($issues.Count -gt 0) {
    $details = ($issues | ForEach-Object { "- $_" }) -join [Environment]::NewLine
    throw "LINE tunnel preflight failed:$([Environment]::NewLine)$details"
}

Write-Host "Starting a temporary Cloudflare Quick Tunnel for http://127.0.0.1:$Port"
Write-Host "Append /api/v1/line/webhook to the trycloudflare.com URL shown below."
Write-Host "Press Ctrl+C to stop the tunnel."
& $cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$Port"
exit $LASTEXITCODE
