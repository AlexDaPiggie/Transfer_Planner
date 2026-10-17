param(
    [int]$Port = 8080
)

$frontendPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Split-Path -Parent $frontendPath
$url = "http://localhost:$Port"
$apiOutputLog = Join-Path $frontendPath ".local-api-output.log"
$apiErrorLog = Join-Path $frontendPath ".local-api-error.log"
$projectPythonPath = Join-Path $projectPath ".venv311\Scripts\python.exe"
$pythonPath = if (Test-Path -LiteralPath $projectPythonPath) { $projectPythonPath } else { (Get-Command python -ErrorAction Stop).Source }

function Test-LocalBackend {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2
        $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 2
        $paths = $openApi.paths.PSObject.Properties.Name
        return $health.status -eq "ok" -and $openApi.info.version -eq "2.1.0" -and $openApi.info.title -eq "Transfer Educational Plan AI Assistant" -and $paths -contains "/api/compass/email-preferences" -and $paths -contains "/api/auth/reset-password"
    } catch {
        return $false
    }
}

$apiProcess = $null
if (Test-LocalBackend) {
    Write-Host "Using the FastAPI server already running at http://127.0.0.1:8000"
} else {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
        throw "Port 8000 is running an older Pathway backend or another service. Stop its terminal with Ctrl+C, then run this launcher again."
    }

    Write-Host "Starting FastAPI at http://127.0.0.1:8000"
    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @("-m", "uvicorn", "backend.model_planner.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload", "--reload-dir", "backend", "--reload-dir", "models") -WorkingDirectory $projectPath -RedirectStandardOutput $apiOutputLog -RedirectStandardError $apiErrorLog -WindowStyle Hidden -PassThru

    $deadline = (Get-Date).AddSeconds(30)
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
try { Push-Location $projectPath; & $pythonPath -m backend.local_frontend --port $Port }
finally { Pop-Location; if ($apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force } }
