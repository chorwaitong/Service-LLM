$TaskName = "Jarvis Service"
$HealthUrl = "http://localhost:8000/health"
$MaxRetries = 10
$RetryIntervalSec = 2

Write-Host "Stopping scheduled task: $TaskName"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

Write-Host "Starting scheduled task: $TaskName"
Start-ScheduledTask -TaskName $TaskName

Write-Host "Waiting for service health check..."

$healthy = $false

for ($i = 1; $i -le $MaxRetries; $i++) {
    try {
        $response = curl.exe -s $HealthUrl
        if ($response -match "ok") {
            Write-Host "Service is healthy."
            $healthy = $true
            break
        }
    } catch {
        # ignore transient failures
    }

    Write-Host "Health check attempt $i failed. Retrying..."
    Start-Sleep -Seconds $RetryIntervalSec
}

if (-not $healthy) {
    Write-Error "Service failed to become healthy after restart."
    exit 1
}

exit 0
