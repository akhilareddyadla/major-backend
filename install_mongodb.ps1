# Download MongoDB installer
$url = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.5-signed.msi"
$output = "$env:TEMP\mongodb.msi"
Write-Host "Downloading MongoDB installer..."
Invoke-WebRequest -Uri $url -OutFile $output

# Install MongoDB
Write-Host "Installing MongoDB..."
Start-Process msiexec.exe -Wait -ArgumentList "/i $output /quiet /qn /norestart"

# Create data directory
$dataPath = "C:\data\db"
if (-not (Test-Path -Path $dataPath)) {
    Write-Host "Creating data directory..."
    New-Item -ItemType Directory -Path $dataPath -Force
}

Write-Host "MongoDB installation completed!"
Write-Host "Please start MongoDB service by running: net start MongoDB" 