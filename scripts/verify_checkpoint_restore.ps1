param(
    [string]$PythonPath = "python",
    [string]$NodePath = "node",
    [int]$Port = 8891
)

$ErrorActionPreference = "Stop"
$FactoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExampleRoot = Join-Path $FactoryRoot "examples\ava-summit-golden-path"
$ManifestPath = Join-Path $FactoryRoot "CHECKPOINT_FILE_SHA256.json"

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Checkpoint manifest is missing."
}

$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $path = Join-Path $FactoryRoot $entry.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Checkpoint file is missing: $($entry.path)"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) {
        throw "Checkpoint hash mismatch: $($entry.path)"
    }
}

$requiredFixturePaths = @(
    "knowledge-package\manifest.v0.1.json",
    "mission\mission-record.json",
    "generated-app\web\app.js"
)
foreach ($relative in $requiredFixturePaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $ExampleRoot $relative))) {
        throw "Ava/Summit fixture is incomplete: $relative"
    }
}

& $NodePath (Join-Path $FactoryRoot "scripts\verify_preview_state_model_v0_1.js") | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Provider-free state-model regression failed."
}

$serverScript = Join-Path $FactoryRoot "scripts\mission_control_server.py"
$quotedServerScript = '"' + $serverScript + '"'
$process = Start-Process -FilePath $PythonPath -ArgumentList @("-B", $quotedServerScript, "--port", $Port) -WorkingDirectory $FactoryRoot -WindowStyle Hidden -PassThru
try {
    $status = $null
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        try {
            $status = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -TimeoutSec 1
            break
        } catch {
            if ($process.HasExited) {
                throw "Mission Control exited before becoming ready."
            }
        }
    }
    if ($null -eq $status) {
        throw "Mission Control did not become ready."
    }
    if ($status.status -ne "READY" -or $status.factory_version -ne "1.9") {
        throw "Unexpected Mission Control status or version."
    }
    if ($status.provider_calls -ne 0) {
        throw "Checkpoint verification attempted provider calls."
    }
    [pscustomobject]@{
        status = "CHECKPOINT_RESTORE_SMOKE_PASS"
        factory_version = $status.factory_version
        provider_calls = $status.provider_calls
        lifecycle = "OWNER_TESTING_BASELINE"
    } | ConvertTo-Json
} finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
