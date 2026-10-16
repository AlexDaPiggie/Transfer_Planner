param(
    [int]$Port = 8080
)

$frontendPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Split-Path -Parent $frontendPath
$url = "http://localhost:$Port"
$apiOutputLog = Join-Path $frontendPath ".local-api-output.log"
$apiErrorLog = Join-Path $frontendPath ".local-api-error.log"
$pythonPath = (Get-Command python -ErrorAction Stop).Source

function Test-LocalBackend {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2
        $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 2
        return $health.status -eq "ok" -and $openApi.info.title -eq "Transfer Educational Plan AI Assistant"
    } catch {
        return $false
    }
}

$apiProcess = $null
if (Test-LocalBackend) {
    Write-Host "Using the FastAPI server already running at http://127.0.0.1:8000"
} else {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
        throw "Port 8000 is in use by another service. Stop it before running this launcher."
    }

    Write-Host "Starting FastAPI at http://127.0.0.1:8000"
    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @("-m", "uvicorn", "backend.model_planner.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $projectPath -RedirectStandardOutput $apiOutputLog -RedirectStandardError $apiErrorLog -WindowStyle Hidden -PassThru

    $deadline = (Get-Date).AddSeconds(15)
    $backendReady = $false
    while ((Get-Date) -lt $deadline) {
        if ($apiProcess.HasExited) {
            throw "The backend stopped while starting. Open $apiErrorLog to see why."
        }
        if (Test-LocalBackend) { $backendReady = $true; break }
        Start-Sleep -Milliseconds 400
    }
    if (-not $backendReady) {
        if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force }
        throw "The backend did not become ready. Open $apiErrorLog to see why."
    }
}

Write-Host "Starting Pathway at $url"
if ($apiProcess) {
    Write-Host "Press Ctrl+C to stop both local servers."
} else {
    Write-Host "Press Ctrl+C to stop the website. The existing FastAPI server will keep running."
}
try { python -m http.server $Port --directory $frontendPath }
finally { if ($apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force } }
