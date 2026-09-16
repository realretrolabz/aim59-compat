<#
.SYNOPSIS
Simple graphical front end for install-aim59.ps1.

.DESCRIPTION
Presents the AIM server choice and invokes install-aim59.ps1 as the sole
installer/patch backend. It contains no AIM download, patch, registry, or
rollback implementation of its own.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function ConvertTo-PowerShellLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)

    return "'" + $Value.Replace("'", "''") + "'"
}

function Start-ElevatedGui {
    $scriptPath = $PSCommandPath
    $arguments = "-NoProfile -ExecutionPolicy Bypass -STA -File `"$scriptPath`""
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments | Out-Null
}

if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') {
    $scriptPath = $PSCommandPath
    $arguments = "-NoProfile -ExecutionPolicy Bypass -STA -File `"$scriptPath`""
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -PassThru -Wait
    exit $process.ExitCode
}

if (-not (Test-IsAdministrator)) {
    Start-ElevatedGui
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$backendPath = Join-Path $PSScriptRoot 'install-aim59.ps1'
if (-not (Test-Path -LiteralPath $backendPath -PathType Leaf)) {
    [System.Windows.Forms.MessageBox]::Show(
        "Backend script not found:`r`n$backendPath",
        'AIM 5.9 setup',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'AIM 5.9 Setup'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = [System.Drawing.Size]::new(520, 475)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false

$title = [System.Windows.Forms.Label]::new()
$title.Text = 'Install and patch AIM 5.9.3861'
$title.Font = [System.Drawing.Font]::new($form.Font, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = [System.Drawing.Point]::new(18, 18)
$form.Controls.Add($title)

$summary = [System.Windows.Forms.Label]::new()
$summary.Text = 'This downloads the verified installer, runs it normally, and disables aimapi.dll by renaming it. The original file can be restored later.'
$summary.Location = [System.Drawing.Point]::new(18, 52)
$summary.Size = [System.Drawing.Size]::new(480, 42)
$form.Controls.Add($summary)

$installerGroup = [System.Windows.Forms.GroupBox]::new()
$installerGroup.Text = 'Installer source'
$installerGroup.Location = [System.Drawing.Point]::new(18, 108)
$installerGroup.Size = [System.Drawing.Size]::new(480, 98)
$form.Controls.Add($installerGroup)

$oldVersion = [System.Windows.Forms.RadioButton]::new()
$oldVersion.Text = 'Download the verified installer from OldVersion.com'
$oldVersion.Checked = $true
$oldVersion.AutoSize = $true
$oldVersion.Location = [System.Drawing.Point]::new(16, 25)
$installerGroup.Controls.Add($oldVersion)

$localInstaller = [System.Windows.Forms.RadioButton]::new()
$localInstaller.Text = 'Use a local AIM 5.9.3861 installer:'
$localInstaller.AutoSize = $true
$localInstaller.Location = [System.Drawing.Point]::new(16, 52)
$installerGroup.Controls.Add($localInstaller)

$installerPathBox = [System.Windows.Forms.TextBox]::new()
$installerPathBox.Enabled = $false
$installerPathBox.Location = [System.Drawing.Point]::new(208, 50)
$installerPathBox.Size = [System.Drawing.Size]::new(174, 23)
$installerGroup.Controls.Add($installerPathBox)

$browseButton = [System.Windows.Forms.Button]::new()
$browseButton.Text = 'Browse...'
$browseButton.Enabled = $false
$browseButton.Location = [System.Drawing.Point]::new(390, 49)
$browseButton.Size = [System.Drawing.Size]::new(72, 25)
$installerGroup.Controls.Add($browseButton)

$localInstaller.add_CheckedChanged({
    $installerPathBox.Enabled = $localInstaller.Checked
    $browseButton.Enabled = $localInstaller.Checked
})

$browseButton.Add_Click({
    $dialog = [System.Windows.Forms.OpenFileDialog]::new()
    $dialog.Title = 'Choose the original AIM 5.9.3861 installer'
    $dialog.Filter = 'AIM installer (aim593861.exe)|aim593861.exe|Executable files (*.exe)|*.exe|All files (*.*)|*.*'
    $dialog.CheckFileExists = $true
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $installerPathBox.Text = $dialog.FileName
    }
    $dialog.Dispose()
})

$serverGroup = [System.Windows.Forms.GroupBox]::new()
$serverGroup.Text = 'AIM server'
$serverGroup.Location = [System.Drawing.Point]::new(18, 220)
$serverGroup.Size = [System.Drawing.Size]::new(480, 145)
$form.Controls.Add($serverGroup)

$realRetro = [System.Windows.Forms.RadioButton]::new()
$realRetro.Text = 'Use aim.realretrolabz.com:5190'
$realRetro.Checked = $true
$realRetro.AutoSize = $true
$realRetro.Location = [System.Drawing.Point]::new(16, 26)
$serverGroup.Controls.Add($realRetro)

$keepDefault = [System.Windows.Forms.RadioButton]::new()
$keepDefault.Text = "Keep AIM's original server setting"
$keepDefault.AutoSize = $true
$keepDefault.Location = [System.Drawing.Point]::new(16, 52)
$serverGroup.Controls.Add($keepDefault)

$custom = [System.Windows.Forms.RadioButton]::new()
$custom.Text = 'Use another server:'
$custom.AutoSize = $true
$custom.Location = [System.Drawing.Point]::new(16, 78)
$serverGroup.Controls.Add($custom)

$hostBox = [System.Windows.Forms.TextBox]::new()
$hostBox.Enabled = $false
$hostBox.Location = [System.Drawing.Point]::new(154, 76)
$hostBox.Size = [System.Drawing.Size]::new(190, 23)
$serverGroup.Controls.Add($hostBox)

$portBox = [System.Windows.Forms.TextBox]::new()
$portBox.Enabled = $false
$portBox.Text = '5190'
$portBox.Location = [System.Drawing.Point]::new(355, 76)
$portBox.Size = [System.Drawing.Size]::new(70, 23)
$serverGroup.Controls.Add($portBox)

$custom.add_CheckedChanged({
    $hostBox.Enabled = $custom.Checked
    $portBox.Enabled = $custom.Checked
    if ($custom.Checked) {
        $hostBox.Focus()
    }
})

$status = [System.Windows.Forms.Label]::new()
$status.Text = 'Ready. The AIM installer will open in its own window.'
$status.Location = [System.Drawing.Point]::new(18, 382)
$status.Size = [System.Drawing.Size]::new(480, 42)
$form.Controls.Add($status)

$installButton = [System.Windows.Forms.Button]::new()
$installButton.Text = 'Install AIM'
$installButton.Location = [System.Drawing.Point]::new(292, 432)
$installButton.Size = [System.Drawing.Size]::new(100, 28)
$form.Controls.Add($installButton)

$rollbackButton = [System.Windows.Forms.Button]::new()
$rollbackButton.Text = 'Restore aimapi.dll'
$rollbackButton.Location = [System.Drawing.Point]::new(148, 432)
$rollbackButton.Size = [System.Drawing.Size]::new(132, 28)
$form.Controls.Add($rollbackButton)

$closeButton = [System.Windows.Forms.Button]::new()
$closeButton.Text = 'Close'
$closeButton.Location = [System.Drawing.Point]::new(404, 432)
$closeButton.Size = [System.Drawing.Size]::new(94, 28)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$script:backendProcess = $null
$script:outputPath = Join-Path $env:TEMP ("aim59-setup-" + [Guid]::NewGuid().ToString('N') + '.out')
$script:errorPath = Join-Path $env:TEMP ("aim59-setup-" + [Guid]::NewGuid().ToString('N') + '.err')

$timer = [System.Windows.Forms.Timer]::new()
$timer.Interval = 300
$timer.Add_Tick({
    if ($null -eq $script:backendProcess -or -not $script:backendProcess.HasExited) {
        return
    }
    $timer.Stop()
    $installButton.Enabled = $true
    $rollbackButton.Enabled = $true
    $closeButton.Enabled = $true
    $details = @()
    if (Test-Path -LiteralPath $script:outputPath) {
        $details += Get-Content -LiteralPath $script:outputPath -Raw -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $script:errorPath) {
        $details += Get-Content -LiteralPath $script:errorPath -Raw -ErrorAction SilentlyContinue
    }
    if ($script:backendProcess.ExitCode -eq 0) {
        $status.Text = 'Completed successfully.'
        [System.Windows.Forms.MessageBox]::Show('AIM setup completed successfully.', 'AIM 5.9 setup') | Out-Null
    }
    else {
        $status.Text = "The backend stopped with exit code $($script:backendProcess.ExitCode)."
        $message = ($details -join "`r`n").Trim()
        if ([string]::IsNullOrWhiteSpace($message)) {
            $message = 'See the PowerShell backend output for details.'
        }
        [System.Windows.Forms.MessageBox]::Show($message, 'AIM 5.9 setup failed', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    }
    Remove-Item -LiteralPath $script:outputPath, $script:errorPath -Force -ErrorAction SilentlyContinue
    $script:backendProcess = $null
})

function Start-BackendProcess {
    param([Parameter(Mandatory = $true)][string]$Command)

    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $script:backendProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand
    ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $script:outputPath -RedirectStandardError $script:errorPath
    $installButton.Enabled = $false
    $rollbackButton.Enabled = $false
    $closeButton.Enabled = $false
    $status.Text = 'Working. Complete the AIM installer window, then this wizard will finish the patch.'
    $timer.Start()
}

$installButton.Add_Click({
    $mode = 'RealRetroLabz'
    $serverHost = $null
    $serverPort = 5190
    if ($keepDefault.Checked) {
        $mode = 'Keep'
    }
    elseif ($custom.Checked) {
        $mode = 'Custom'
        $serverHost = $hostBox.Text.Trim()
        if ([string]::IsNullOrWhiteSpace($serverHost)) {
            [System.Windows.Forms.MessageBox]::Show('Enter a server host.', 'AIM 5.9 setup', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
            return
        }
        if (-not [int]::TryParse($portBox.Text.Trim(), [ref]$serverPort) -or $serverPort -lt 1 -or $serverPort -gt 65535) {
            [System.Windows.Forms.MessageBox]::Show('Enter a port from 1 through 65535.', 'AIM 5.9 setup', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
            return
        }
    }
    $installerPath = $null
    if ($localInstaller.Checked) {
        $installerPath = $installerPathBox.Text.Trim()
        if ([string]::IsNullOrWhiteSpace($installerPath)) {
            [System.Windows.Forms.MessageBox]::Show('Choose the original AIM installer file.', 'AIM 5.9 setup', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
            return
        }
    }
    $command = "& " + (ConvertTo-PowerShellLiteral $backendPath) + " -ServerMode " + (ConvertTo-PowerShellLiteral $mode)
    if ($mode -eq 'Custom') {
        $command += " -ServerHost " + (ConvertTo-PowerShellLiteral $serverHost) + " -ServerPort $serverPort"
    }
    if ($null -ne $installerPath) {
        $command += " -InstallerPath " + (ConvertTo-PowerShellLiteral $installerPath)
    }
    Start-BackendProcess -Command $command
})

$rollbackButton.Add_Click({
    $answer = [System.Windows.Forms.MessageBox]::Show(
        'Restore the aimapi.dll file that this tool renamed?',
        'Restore aimapi.dll',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
        return
    }
    $command = "& " + (ConvertTo-PowerShellLiteral $backendPath) + ' -Rollback'
    Start-BackendProcess -Command $command
})

$form.Add_FormClosed({
    if ($null -ne $script:backendProcess -and -not $script:backendProcess.HasExited) {
        $script:backendProcess.Dispose()
    }
    Remove-Item -LiteralPath $script:outputPath, $script:errorPath -Force -ErrorAction SilentlyContinue
})

[void]$form.ShowDialog()
