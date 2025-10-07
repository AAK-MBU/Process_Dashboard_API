Write-Host "Setting up API keys in Docker container..." -ForegroundColor Green

$containerName = "process-dashboard-api"
$containerRunning = docker ps --filter "name=$containerName" --filter "status=running" -q

if (-not $containerRunning) {
    Write-Host "Container '$containerName' is not running!" -ForegroundColor Red
    Write-Host "Start the container first with: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}

Write-Host "Container is running. Executing API key setup..." -ForegroundColor Green

docker exec $containerName python scripts/docker_setup_api_keys.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "API key setup completed successfully!" -ForegroundColor Green
    
    $apiKeyFile = docker exec $containerName cat /tmp/api_key.txt 2>$null
    if ($apiKeyFile) {
        Write-Host ""
        Write-Host "API Key Details:" -ForegroundColor Cyan
        Write-Host $apiKeyFile -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Save this information securely!" -ForegroundColor Red
    }
} else {
    Write-Host "API key setup failed!" -ForegroundColor Red
    exit 1
}