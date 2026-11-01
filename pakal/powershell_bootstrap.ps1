# PowerShell 7 + NuGet bootstrap. Placeholders are replaced by pakal.powershell_setup.
# The portal shows this script and copies a one-line pwsh -Command that runs it.
[CmdletBinding()]
param(
    [string]$NuGetExeSourcePath = __NUGET_SOURCE__,
    [string]$RepoName = __REPO_NAME__,
    [string]$RepoUrl = __REPO_URL__,
    [string]$Policy = 'Trusted'
)

$ErrorActionPreference = 'Stop'

function Install-NuGetExeForUser {
    $destDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\PowerShell\PowerShellGet'
    $destPath = Join-Path $destDir 'nuget.exe'

    if (Test-Path -LiteralPath $destPath) {
        Write-Host "[SKIP] nuget.exe already present at $destPath" -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path -LiteralPath $NuGetExeSourcePath)) {
        throw "Cannot find source nuget.exe at $NuGetExeSourcePath -- Check network connection to SMB share."
    }

    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Copy-Item -LiteralPath $NuGetExeSourcePath -Destination $destPath -Force
    Write-Host "[OK]   Copied nuget.exe -> $destPath" -ForegroundColor Green
}

function Register-NexusRepository {
    $existing = Get-PSRepository -Name $RepoName -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.SourceLocation -eq $RepoUrl) {
            Write-Host "[SKIP] '$RepoName' already registered and up to date." -ForegroundColor Yellow
            return
        }
        Set-PSRepository -Name $RepoName -SourceLocation $RepoUrl -PublishLocation $RepoUrl -ScriptSourceLocation $RepoUrl -ScriptPublishLocation $RepoUrl -InstallationPolicy $Policy
        Write-Host "[OK]   '$RepoName' config updated." -ForegroundColor Green
        return
    }

    Register-PSRepository -Name $RepoName -SourceLocation $RepoUrl -PublishLocation $RepoUrl -ScriptSourceLocation $RepoUrl -ScriptPublishLocation $RepoUrl -InstallationPolicy $Policy -ErrorAction Stop
    Write-Host "[OK]   '$RepoName' registered -> $RepoUrl" -ForegroundColor Green
}

Install-NuGetExeForUser
Register-NexusRepository
