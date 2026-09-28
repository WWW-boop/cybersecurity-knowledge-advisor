#Requires -Version 5.1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolDirectory = Join-Path $projectRoot ".tools\cloudflared"
$target = Join-Path $toolDirectory "cloudflared.exe"
$download = Join-Path $toolDirectory "cloudflared.exe.download"

if (Test-Path -LiteralPath $target -PathType Leaf) {
    Write-Host "cloudflared is already installed at $target"
    & $target --version
    exit $LASTEXITCODE
}

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
$assetArchitecture = switch ($architecture) {
    "X64" { "amd64" }
    "Arm64" { "arm64" }
    default { throw "Unsupported Windows architecture: $architecture" }
}
$assetName = "cloudflared-windows-$assetArchitecture.exe"
$headers = @{
    "User-Agent" = "cybersecurity-knowledge-advisor-setup"
    "Accept" = "application/vnd.github+json"
}

New-Item -ItemType Directory -Path $toolDirectory -Force | Out-Null
try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/cloudflare/cloudflared/releases/latest" `
        -Headers $headers
    $asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
    if ($null -eq $asset) {
        throw "Official release asset not found: $assetName"
    }
    if ($asset.digest -notmatch "^sha256:([0-9a-fA-F]{64})$") {
        throw "The official release did not provide a SHA-256 digest"
    }
    $expectedHash = $Matches[1].ToLowerInvariant()

    Invoke-WebRequest `
        -Uri $asset.browser_download_url `
        -Headers $headers `
        -OutFile $download `
        -UseBasicParsing
    $actualHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "cloudflared SHA-256 mismatch"
    }

    Move-Item -LiteralPath $download -Destination $target
    Write-Host "Installed cloudflared $($release.tag_name)"
    Write-Host "SHA-256: $actualHash"
    & $target --version
} finally {
    if (Test-Path -LiteralPath $download) {
        Remove-Item -LiteralPath $download -Force
    }
}
