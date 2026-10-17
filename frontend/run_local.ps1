param(
    [int]$Port = 8080,
    [Alias("r")]
    [switch]$Restart
)

$frontendPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Split-Path -Parent $frontendPath
$url = "http://localhost:$Port"
$apiPort = 8000
$apiUrl = "http://127.0.0.1:$apiPort"
$apiOutputLog = Join-Path $frontendPath ".local-api-output.log"
$apiErrorLog = Join-Path $frontendPath ".local-api-error.log"
$apiPidFile = Join-Path $frontendPath ".local-api.pid"
$projectPythonPath = Join-Path $projectPath ".venv311\Scripts\python.exe"
$pythonPath = if (Test-Path -LiteralPath $projectPythonPath) { $projectPythonPath } else { (Get-Command python -ErrorAction Stop).Source }

function Get-TrackedBackendProcess {
    if (-not (Test-Path -LiteralPath $apiPidFile)) { return $null }
    $rawPid = [string](Get-Content -LiteralPath $apiPidFile -Raw -ErrorAction SilentlyContinue)
    $processId = 0
    if (-not [int]::TryParse($rawPid.Trim(), [ref]$processId)) {
        Remove-Item -LiteralPath $apiPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -LiteralPath $apiPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    return $process
}

function Get-ListeningProcess {
    $listener = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return $null }
    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    return [PSCustomObject]@{ Id = $listener.OwningProcess; Name = if ($process) { $process.ProcessName } else { "unknown" } }
}

function Stop-TrackedBackend([System.Diagnostics.Process]$Process) {
    # Stop the process tree started by this launcher, never an arbitrary listener.
    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ParentProcessId -eq $Process.Id }
    foreach ($child in $children) {
        $childProcess = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
        if ($childProcess) { Stop-TrackedBackend $childProcess }
    }
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(5000) | Out-Null
    }
}

function Remove-TrackedPid([int]$ExpectedPid) {
    if (-not (Test-Path -LiteralPath $apiPidFile)) { return }
    $storedPid = ([string](Get-Content -LiteralPath $apiPidFile -Raw -ErrorAction SilentlyContinue)).Trim()
    if ($storedPid -eq "$ExpectedPid") {
        Remove-Item -LiteralPath $apiPidFile -Force -ErrorAction SilentlyContinue
    }
}

function Test-LocalBackend {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/api/health" -TimeoutSec 2
        $openApi = Invoke-RestMethod -Uri "$apiUrl/openapi.json" -TimeoutSec 2
        $paths = $openApi.paths.PSObject.Properties.Name
        return $health.status -eq "ok" -and $openApi.info.version -eq "2.1.0" -and $openApi.info.title -eq "De Anza Guide" -and $paths -contains "/api/compass/email-preferences" -and $paths -contains "/api/auth/reset-password"
    } catch {
        return $false
    }
}

function Wait-ForPortToClose {
    $deadline = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-ListeningProcess)) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "The backend process did not release port $apiPort. Check Task Manager, then try again."
}

function Stop-AdoptedBackend {
    # This path is used only after Test-LocalBackend confirms that the
    # listener is De Anza Guide. It supports servers started before PID
    # tracking was added to this launcher.
    $listener = Get-ListeningProcess
    if (-not $listener) { return }
    try {
        Stop-Process -Id $listener.Id -Force -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "Windows denied permission to stop the verified De Anza Guide backend (PID $($listener.Id)). The launcher will use that healthy backend."
        return $false
    }
}

function Start-LocalBackend {
    Write-Host "Starting FastAPI at $apiUrl"
    $process = Start-Process -FilePath $pythonPath -ArgumentList @("-m", "uvicorn", "backend.model_planner.main:app", "--host", "127.0.0.1", "--port", "$apiPort", "--reload", "--reload-dir", "backend", "--reload-dir", "models") -WorkingDirectory $projectPath -RedirectStandardOutput $apiOutputLog -RedirectStandardError $apiErrorLog -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $apiPidFile -Value $process.Id -NoNewline

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) {
            Remove-TrackedPid $process.Id
            throw "The backend stopped while starting. Open $apiErrorLog to see why."
        }
        if (Test-LocalBackend) { return $process }
        Start-Sleep -Milliseconds 400
    }
    Stop-TrackedBackend $process
    Remove-TrackedPid $process.Id
    throw "The backend did not become ready. Open $apiErrorLog to see why."
}

$apiProcess = $null
$trackedProcess = Get-TrackedBackendProcess
$backendReady = Test-LocalBackend

if ($Restart) {
    if ($trackedProcess) {
        Write-Host "Restarting the FastAPI server previously started by this launcher (PID $($trackedProcess.Id))."
        Stop-TrackedBackend $trackedProcess
        Remove-TrackedPid $trackedProcess.Id
        Wait-ForPortToClose
        $backendReady = $false
    } elseif (Get-ListeningProcess) {
        if (Test-LocalBackend) {
            $listener = Get-ListeningProcess
            Write-Host "Checking whether the existing De Anza Guide backend (PID $($listener.Id)) can be restarted."
            if (Stop-AdoptedBackend) {
                Wait-ForPortToClose
                $backendReady = $false
            } else {
                $backendReady = Test-LocalBackend
                if (-not $backendReady) {
                    throw "The existing De Anza Guide backend stopped responding after the restart attempt. Run this command again."
                }
                Write-Host "Restart skipped; using the existing backend at $apiUrl."
            }
        } else {
            $listener = Get-ListeningProcess
            throw "Port $apiPort is used by $($listener.Name) (PID $($listener.Id)), not a De Anza Guide backend. It was not stopped."
        }
    }
}

if ($backendReady) {
    Write-Host "Using the FastAPI server already running at $apiUrl"
} else {
    $listener = Get-ListeningProcess
    if ($listener) {
        if ($trackedProcess) {
            Write-Host "Restarting an unhealthy FastAPI server previously started by this launcher (PID $($trackedProcess.Id))."
            Stop-TrackedBackend $trackedProcess
            Remove-TrackedPid $trackedProcess.Id
            Wait-ForPortToClose
        } else {
            throw "Port $apiPort is used by $($listener.Name) (PID $($listener.Id)), but it is not a current De Anza Guide backend. It was not stopped."
        }
    }
    $apiProcess = Start-LocalBackend
}

Write-Host "Starting De Anza Guide at $url"
if ($apiProcess) {
    Write-Host "Press Ctrl+C to stop the website and the backend started by this launcher."
} else {
    Write-Host "Press Ctrl+C to stop the website. The existing FastAPI server will keep running."
}
try { Push-Location $projectPath; & $pythonPath -m backend.local_frontend --port $Port }
finally {
    Pop-Location
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-TrackedBackend $apiProcess
        Remove-TrackedPid $apiProcess.Id
    }
}
