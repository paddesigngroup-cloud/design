Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$git = "git"
if (Test-Path "C:\\Program Files\\Git\\cmd\\git.exe") {
  $git = "C:\\Program Files\\Git\\cmd\\git.exe"
}

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args
  )
  & $git @Args
  return $LASTEXITCODE
}

Push-Location $repoRoot
try {
  $exit = Invoke-Git -Args @("rev-parse", "--is-inside-work-tree")
  if ($exit -ne 0) { throw "Not a git repository: $repoRoot" }

  Write-Host "Auto-push is running in: $repoRoot"
  Write-Host "Press Ctrl+C to stop."

  $watcher = New-Object System.IO.FileSystemWatcher
  $watcher.Path = $repoRoot
  $watcher.IncludeSubdirectories = $true
  $watcher.NotifyFilter = [System.IO.NotifyFilters]'FileName, LastWrite, DirectoryName'
  $watcher.EnableRaisingEvents = $true

  $script:lastEventAt = Get-Date "2000-01-01"

  $handler = {
    $path = $Event.SourceEventArgs.FullPath
    $rel = $path.Substring($repoRoot.Length).TrimStart('\','/')

    if ($rel -match '^(\\.git|\\.venv|node_modules)(\\\\|/|$)') { return }
    if ($rel -match '\\.log$') { return }

    $script:lastEventAt = Get-Date
  }

  $created = Register-ObjectEvent -InputObject $watcher -EventName Created -Action $handler
  $changed = Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $handler
  $deleted = Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $handler
  $renamed = Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $handler

  while ($true) {
    Start-Sleep -Milliseconds 500

    $idleSeconds = ((Get-Date) - $script:lastEventAt).TotalSeconds
    if ($idleSeconds -lt 2) { continue }
    if ($script:lastEventAt -lt (Get-Date).AddYears(-1)) { continue }

    # Reset marker before running git to avoid event storms.
    $script:lastEventAt = Get-Date "2000-01-01"

    # Only commit/push when there are tracked changes.
    $status = & $git status --porcelain
    if (-not $status) { continue }

    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "Detected changes -> committing & pushing ($ts)..."

    Invoke-Git -Args @("add", "-A") | Out-Null

    & $git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { continue } # nothing staged (e.g., only ignored files)

    Invoke-Git -Args @("commit", "-m", "Auto: $ts") | Out-Null
    Invoke-Git -Args @("push") | Out-Null

    Write-Host "Pushed."
  }
}
finally {
  Pop-Location
}

