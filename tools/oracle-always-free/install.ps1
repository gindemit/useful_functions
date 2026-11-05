$ErrorActionPreference = 'Stop'
$root = 'C:\Work\projects\oracle'
$data = Join-Path $env:LOCALAPPDATA 'MediaService'
$taskName = 'MediaService-OCI-AlwaysFree-A1'
$task = Get-ScheduledTask -TaskName $taskName
if ($task.State -eq 'Running') { throw 'Wait for the active Oracle run to finish before installing.' }
$backup = Join-Path $data ('monitor-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $backup 'task.xml')
$script = Join-Path $root 'provision-oci-always-free-a1.ps1'
Copy-Item -LiteralPath $script -Destination $backup
$source = Get-Content -LiteralPath $script -Raw

# Capture RUNNING before the existing email delivery, which can fail independently.
$hook = @'
function Write-RunningInstance {
    param([object]$Instance)
    $record = @{
        instance_id = $Instance.id
        name = $Instance.'display-name'
        observed = (Get-Date).ToString('o')
    }
    $destination = Join-Path $LogDirectory 'oci-a1-running.json'
    $temporary = "$destination.tmp"
    $record | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination -Force
    Write-Log 'Instance confirmed RUNNING; recorded for Telegram notification.'
}

'@
if (-not $source.Contains('function Write-RunningInstance {')) {
    $source = $source.Replace('function Send-SuccessNotification {', $hook + "`r`nfunction Send-SuccessNotification {")
    $needle = '            $publicIp = Get-InstancePublicIp -InstanceId $named[0].id'
    if (-not $source.Contains($needle)) { throw 'Existing-instance hook location changed.' }
    $source = $source.Replace($needle, '            Write-RunningInstance -Instance $named[0]' + "`r`n" + $needle)
    $needle = '            $instance = $instanceResponse.data'
    if (-not $source.Contains($needle)) { throw 'New-instance hook location changed.' }
    $source = $source.Replace($needle, $needle + "`r`n" + '            Write-RunningInstance -Instance $instance')
    # Preserve complete OCI authentication/error details under Windows PowerShell.
    $needle = '    $output = & oci @Arguments 2>&1'
    if (-not $source.Contains($needle)) { throw 'OCI helper location changed.' }
    $source = $source.Replace($needle, @'
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & oci @Arguments 2>&1
        $ociExitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previousPreference }
'@)
    $source = [regex]::Replace($source, '(?m)^    if \(\$LASTEXITCODE -ne 0\) \{', '    if ($ociExitCode -ne 0) {')
    # Only Invoke-OciJson uses this exact indentation; the RUNNING waiter remains unchanged.
    $tokens = $null; $errors = $null
    [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ($errors | Out-String) }
    Set-Content -LiteralPath $script -Value $source -Encoding UTF8
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'monitor.py') -Destination (Join-Path $root 'monitor.py')
$pythonw = (Get-Command pythonw.exe).Source
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + (Join-Path $root 'monitor.py') + '" check') -WorkingDirectory $root
Set-ScheduledTask -TaskName $taskName -Action $action | Out-Null

# Hourly reporter checks the daily due marker; first send at/after 20:00 local time.
# Independent of provisioning so a disabled/broken provisioning task is observable.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddDays(1).AddHours(20) -RepetitionInterval (New-TimeSpan -Hours 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$report = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + (Join-Path $root 'monitor.py') + '" report') -WorkingDirectory $root
Register-ScheduledTask -TaskName 'MediaService-OCI-DailyStatus' -Action $report -Trigger $trigger -Settings $settings -Principal $task.Principal -Description 'Windowless Oracle daily Telegram summary after 20:00 local time; retries due check hourly when logged in.' -Force | Out-Null
Write-Output "Installed windowless Oracle monitor. Backup: $backup"
