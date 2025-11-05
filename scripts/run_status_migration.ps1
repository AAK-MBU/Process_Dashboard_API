# PowerShell script to run the status column migration

Write-Host "Running status column length migration..." -ForegroundColor Yellow

try {
    # Read the migration script
    $migrationScript = Get-Content -Path "scripts\migrations\002_increase_status_column_length.sql" -Raw
    
    # Run the migration using sqlcmd (requires SQL Server command line tools)
    # Adjust connection parameters as needed
    $server = "172.17.64.1"  # From your .env file
    $database = "ProcessVisualization"
    $username = "mbusqlrpa001"
    $password = "osx#T\2Cvs88"
    
    Write-Host "Connecting to SQL Server: $server" -ForegroundColor Cyan
    
    # Execute the migration
    sqlcmd -S $server -d $database -U $username -P $password -Q $migrationScript
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Migration completed successfully!" -ForegroundColor Green
        Write-Host "Status columns have been increased to VARCHAR(20)" -ForegroundColor Green
    } else {
        Write-Host "Migration failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} catch {
    Write-Host "Error running migration: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please run the SQL script manually:" -ForegroundColor Yellow
    Write-Host "scripts\migrations\002_increase_status_column_length.sql" -ForegroundColor Yellow
}

Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")