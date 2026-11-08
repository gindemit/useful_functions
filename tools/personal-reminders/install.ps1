param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Title,
    [Parameter(Mandatory=$true)][string]$Message,
    [int[]]$Hours = @(9, 15, 22),
    [ValidateRange(1, 31)][int]$Days = 7,
    [switch]$Preview
)
$ErrorActionPreference = 'Stop'
if ($Name -notmatch '^[a-z0-9-]+$') { throw 'Name must contain lowercase letters, digits and hyphens.' }
if ((Get-TimeZone).Id -ne 'W. Europe Standard Time') { throw 'This installer requires the Berlin Windows timezone.' }
if (!$Hours.Count -or ($Hours | Where-Object { $_ -lt 0 -or $_ -gt 23 })) { throw 'Hours must be between 0 and 23.' }
$taskName = "AI-Notifications-$Name"
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw "Task already exists: $taskName" }
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonw)) { throw 'pythonw.exe is required for silent execution.' }
$helper = Join-Path $env:USERPROFILE '.codex\skills\telegram-notify\scripts\send_notification.py'
if (!(Test-Path -LiteralPath $helper)) { throw 'Install telegram-notify first.' }
$start = (Get-Date).Date
$end = $start.AddDays($Days)
$config = @{
    start_date = $start.ToString('yyyy-MM-dd'); days = $Days
    hours = @($Hours | Sort-Object -Unique); timezone = 'Europe/Berlin'
    helper = $helper; title = $Title; message = $Message; project = 'Personal reminder'
}
if ($Preview) { $config | ConvertTo-Json; return }
$directory = Join-Path $env:LOCALAPPDATA "AI-Notifications\$Name"
if (Test-Path -LiteralPath $directory) { throw "Reminder directory already exists: $directory" }
New-Item -ItemType Directory -Path $directory | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'remind.py') -Destination $directory
$configPath = Join-Path $directory 'config.json'
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
$triggers = foreach ($hour in $config.hours) {
    $trigger = New-ScheduledTaskTrigger -Daily -At $start.AddHours($hour)
    $trigger.EndBoundary = $end.ToString('yyyy-MM-ddTHH:mm:ss')
    $trigger
}
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"{0}" --config "{1}"' -f (Join-Path $directory 'remind.py'), $configPath) -WorkingDirectory $directory
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
$settings.DisallowStartIfOnBatteries = $false
$settings.StopIfGoingOnBatteries = $false
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description "Personal Telegram reminder; expires $($end.ToString('yyyy-MM-dd')) Europe/Berlin" | Select-Object TaskName, State
Write-Output "Config: $configPath"
Write-Output "Expires: $($end.ToString('yyyy-MM-dd HH:mm')) Europe/Berlin"
