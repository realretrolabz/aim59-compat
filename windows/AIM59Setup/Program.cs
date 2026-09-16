using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Security.Principal;
using System.Text;
using System.Windows.Forms;

namespace AIM59Setup
{
    internal static class Program
    {
        internal const string ApplicationName = "realretrolabz AIM Manager";

        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            if (!IsAdministrator())
            {
                RelaunchElevated();
                return;
            }

            Application.Run(new SetupForm());
        }

        private static bool IsAdministrator()
        {
            WindowsIdentity identity = WindowsIdentity.GetCurrent();
            WindowsPrincipal principal = new WindowsPrincipal(identity);
            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }

        private static void RelaunchElevated()
        {
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = Application.ExecutablePath,
                WorkingDirectory = AppContext.BaseDirectory,
                UseShellExecute = true,
                Verb = "runas"
            };

            try
            {
                Process.Start(startInfo);
            }
            catch (Win32Exception error)
            {
                string message = error.NativeErrorCode == 1223
                    ? "Administrator permission was not granted. AIM setup did not start."
                    : "AIM setup could not request administrator permission.\r\n\r\n" + error.Message;
                MessageBox.Show(message, ApplicationName, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    internal enum OperationKind
    {
        Install,
        Restore,
        ApplyServer,
        Uninstall
    }

    internal sealed class SetupOperation
    {
        internal SetupOperation(OperationKind kind, InstallRequest installRequest)
        {
            Kind = kind;
            InstallRequest = installRequest;
        }

        internal OperationKind Kind { get; private set; }

        internal InstallRequest InstallRequest { get; private set; }
    }

    internal sealed class SetupForm : Form
    {
        private readonly BackgroundWorker operationWorker;
        private readonly RadioButton downloadInstaller;
        private readonly RadioButton localInstaller;
        private readonly TextBox installerPath;
        private readonly Button browseButton;
        private readonly CheckBox removeAolDesktopShortcut;
        private readonly RadioButton realRetroLabz;
        private readonly RadioButton keepAIMDefault;
        private readonly RadioButton customServer;
        private readonly TextBox serverHost;
        private readonly TextBox serverPort;
        private readonly Label status;
        private readonly ProgressBar downloadProgress;
        private readonly TextBox details;
        private readonly Button installButton;
        private readonly Button applyServerButton;
        private readonly Button restoreButton;
        private readonly Button uninstallButton;
        private readonly Button closeButton;
        private readonly StringBuilder operationOutput;
        private readonly object outputLock;
        private bool operationRunning;

        internal SetupForm()
        {
            operationOutput = new StringBuilder();
            outputLock = new object();
            operationWorker = new BackgroundWorker();
            operationWorker.DoWork += OperationWorker_DoWork;
            operationWorker.RunWorkerCompleted += OperationWorker_RunWorkerCompleted;

            Text = Program.ApplicationName;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1060, 790);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            try
            {
                Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            }
            catch (SystemException)
            {
                // The executable still has its embedded icon; retain the standard form icon if extraction fails.
            }

            Label banner = new Label
            {
                Font = new Font("Consolas", 8.25F, FontStyle.Bold),
                BackColor = Color.Black,
                ForeColor = Color.FromArgb(0, 255, 0),
                Location = new Point(18, 4),
                Size = new Size(1024, 121),
                Text = @"
                                   ██                         ▓██                          ▓██               ██▒
                                   ██                         ▓██                          ▓██               ██▒
 ░███████▒ ██████████  ██████████  ██    ████████ ██████████  ▓█████▓ ▒███████░ ██████████ ▓██   ▓█████████▓ ██████████  ██████████
 ▓██       ██      ██          ██  ██    ██       ██▒     ██  ▓██     ▓██      ░██     ▒██ ▓██           ██▓ ██▒     ██░      ████
 ▓██       ██████████  ██████████  ██    ██       ██████████  ▓██     ▓██      ░██     ▒██ ▓██   ▓█████████▓ ██▒     ██░   ▓███░
 ▓██       ██          ██▒     ██  ██    ██       ██▒         ▓██     ▓██      ░██     ▒██ ▓██   ▓██     ██▓ ██▒     ██░ ████
 ▓██       ░█████████   █████████  ▒███░ ██        █████████   █████▓ ▓██       ▓████████   ████  █████████▓ █████████▓  ██████████
                                                                                                                                     █████████████"
            };
            Controls.Add(banner);

            Label title = new Label
            {
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold),
                Location = new Point(18, 133),
                Text = "Install and patch AIM 5.9.3861"
            };
            Controls.Add(title);

            Label summary = new Label
            {
                Font = new Font(Font.FontFamily, 8.25F, FontStyle.Regular),
                Location = new Point(18, 165),
                Size = new Size(1024, 54),
                Text = "Windows 10/11 AOL Instant Messenger installer/management tool (tested in Windows 11). This tool verifies the original installer, runs it, makes a reversible aimapi.dll compatibility change, and optionally sets the server of your choice in the registry.\r\nNote: Saving server changes in the AIM GUI overwrites that setting. Enter the server manually in AIM or run this tool again and select Apply Server Setting."
            };
            Controls.Add(summary);

            GroupBox installerGroup = new GroupBox
            {
                Text = "Installer source",
                Location = new Point(18, 231),
                Size = new Size(1024, 128)
            };
            Controls.Add(installerGroup);

            downloadInstaller = new RadioButton
            {
                AutoSize = true,
                Checked = true,
                Location = new Point(16, 25),
                Text = "Download the verified installer from OldVersion.com"
            };
            installerGroup.Controls.Add(downloadInstaller);

            localInstaller = new RadioButton
            {
                AutoSize = true,
                Location = new Point(16, 55),
                Text = "Use a local original AIM 5.9.3861 installer:"
            };
            localInstaller.CheckedChanged += LocalInstaller_CheckedChanged;
            installerGroup.Controls.Add(localInstaller);

            installerPath = new TextBox
            {
                Enabled = false,
                Location = new Point(279, 53),
                Size = new Size(207, 23)
            };
            installerGroup.Controls.Add(installerPath);

            browseButton = new Button
            {
                Enabled = false,
                Location = new Point(494, 51),
                Size = new Size(84, 26),
                Text = "Browse..."
            };
            browseButton.Click += BrowseButton_Click;
            installerGroup.Controls.Add(browseButton);

            removeAolDesktopShortcut = new CheckBox
            {
                AutoSize = true,
                Checked = false,
                Location = new Point(16, 84),
                Text = "Remove 'Free AOL && Unlimited Internet' desktop shortcut after installation"
            };
            installerGroup.Controls.Add(removeAolDesktopShortcut);

            GroupBox serverGroup = new GroupBox
            {
                Text = "AIM server",
                Location = new Point(18, 371),
                Size = new Size(1024, 146)
            };
            Controls.Add(serverGroup);

            realRetroLabz = new RadioButton
            {
                AutoSize = true,
                Checked = true,
                Location = new Point(16, 26),
                Text = "Use aim.realretrolabz.com:5190"
            };
            serverGroup.Controls.Add(realRetroLabz);

            keepAIMDefault = new RadioButton
            {
                AutoSize = true,
                Location = new Point(16, 53),
                Text = "Keep AIM's original server setting"
            };
            serverGroup.Controls.Add(keepAIMDefault);

            customServer = new RadioButton
            {
                AutoSize = true,
                Location = new Point(16, 80),
                Text = "Use another server:"
            };
            customServer.CheckedChanged += CustomServer_CheckedChanged;
            serverGroup.Controls.Add(customServer);

            Label hostLabel = new Label
            {
                AutoSize = true,
                Location = new Point(164, 81),
                Text = "Host:"
            };
            serverGroup.Controls.Add(hostLabel);

            serverHost = new TextBox
            {
                Enabled = false,
                Location = new Point(204, 78),
                Size = new Size(205, 23)
            };
            serverGroup.Controls.Add(serverHost);

            Label portLabel = new Label
            {
                AutoSize = true,
                Location = new Point(418, 81),
                Text = "Port:"
            };
            serverGroup.Controls.Add(portLabel);

            serverPort = new TextBox
            {
                Enabled = false,
                Location = new Point(454, 78),
                Size = new Size(75, 23),
                Text = NativeWorkflow.DefaultServerPort.ToString()
            };
            serverGroup.Controls.Add(serverPort);

            Label customHint = new Label
            {
                AutoSize = true,
                Location = new Point(165, 106),
                Text = "Host and port are saved without network validation."
            };
            serverGroup.Controls.Add(customHint);

            status = new Label
            {
                Location = new Point(18, 530),
                Size = new Size(1024, 26),
                Text = "Ready. Install AIM, apply a server setting, restore aimapi.dll, or start AIM's uninstaller.",
                ForeColor = SystemColors.ControlText
            };
            Controls.Add(status);

            downloadProgress = new ProgressBar
            {
                Location = new Point(18, 560),
                Maximum = 100,
                Minimum = 0,
                Size = new Size(1024, 17),
                Visible = false
            };
            Controls.Add(downloadProgress);

            Label detailsLabel = new Label
            {
                AutoSize = true,
                Location = new Point(18, 588),
                Text = "Setup status and details"
            };
            Controls.Add(detailsLabel);

            details = new TextBox
            {
                Location = new Point(18, 610),
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Size = new Size(1024, 104)
            };
            Controls.Add(details);

            applyServerButton = new Button
            {
                Location = new Point(310, 740),
                Size = new Size(155, 30),
                Text = "Apply server setting"
            };
            applyServerButton.Click += ApplyServerButton_Click;
            Controls.Add(applyServerButton);

            restoreButton = new Button
            {
                Location = new Point(477, 740),
                Size = new Size(142, 30),
                Text = "Restore aimapi.dll"
            };
            restoreButton.Click += RestoreButton_Click;
            Controls.Add(restoreButton);

            uninstallButton = new Button
            {
                Location = new Point(631, 740),
                Size = new Size(145, 30),
                Text = "Uninstall AIM..."
            };
            uninstallButton.Click += UninstallButton_Click;
            Controls.Add(uninstallButton);

            installButton = new Button
            {
                Location = new Point(788, 740),
                Size = new Size(112, 30),
                Text = "Install AIM"
            };
            installButton.Click += InstallButton_Click;
            Controls.Add(installButton);

            closeButton = new Button
            {
                DialogResult = DialogResult.Cancel,
                Location = new Point(912, 740),
                Size = new Size(118, 30),
                Text = "Close"
            };
            closeButton.Click += CloseButton_Click;
            Controls.Add(closeButton);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (operationRunning)
            {
                DialogResult answer = MessageBox.Show(
                    "Close realretrolabz AIM Manager and stop its compatibility workflow? If AIM's original installer is already open, close that window separately. Compatibility changes will not finish after this setup closes.",
                    "Close " + Program.ApplicationName,
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Warning);
                if (answer != DialogResult.Yes)
                {
                    e.Cancel = true;
                }
            }

            base.OnFormClosing(e);
        }

        private void LocalInstaller_CheckedChanged(object sender, EventArgs e)
        {
            installerPath.Enabled = localInstaller.Checked;
            browseButton.Enabled = localInstaller.Checked;
        }

        private void BrowseButton_Click(object sender, EventArgs e)
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "Choose the original AIM 5.9.3861 installer";
                dialog.Filter = "AIM installer (aim593861.exe)|aim593861.exe|Executable files (*.exe)|*.exe|All files (*.*)|*.*";
                dialog.CheckFileExists = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    installerPath.Text = dialog.FileName;
                }
            }
        }

        private void CustomServer_CheckedChanged(object sender, EventArgs e)
        {
            serverHost.Enabled = customServer.Checked;
            serverPort.Enabled = customServer.Checked;
            if (customServer.Checked)
            {
                serverHost.Focus();
            }
        }

        private void InstallButton_Click(object sender, EventArgs e)
        {
            InstallRequest request = BuildInstallRequest();
            if (request == null)
            {
                return;
            }

            RunOperation(
                new SetupOperation(OperationKind.Install, request),
                "Working. The original AIM installer will open in its own window.");
        }

        private InstallRequest BuildInstallRequest()
        {
            InstallRequest request = BuildServerRequest();
            if (request == null)
            {
                return null;
            }
            request.InstallerSource = localInstaller.Checked ? InstallerSource.LocalFile : InstallerSource.OldVersion;
            request.InstallerPath = localInstaller.Checked ? installerPath.Text.Trim() : null;
            request.RemoveAolDesktopShortcut = removeAolDesktopShortcut.Checked;

            if (request.InstallerSource == InstallerSource.LocalFile && request.InstallerPath.Length == 0)
            {
                ShowInputWarning("Choose the original AIM installer file.");
                return null;
            }
            return request;
        }

        private InstallRequest BuildServerRequest()
        {
            InstallRequest request = new InstallRequest();
            if (realRetroLabz.Checked)
            {
                request.ServerMode = ServerMode.RealRetroLabz;
                request.ServerHost = NativeWorkflow.DefaultServerHost;
                request.ServerPort = NativeWorkflow.DefaultServerPort;
            }
            else if (keepAIMDefault.Checked)
            {
                request.ServerMode = ServerMode.Keep;
                request.ServerPort = NativeWorkflow.DefaultServerPort;
            }
            else
            {
                int port;
                string host = serverHost.Text.Trim();
                if (host.Length == 0)
                {
                    ShowInputWarning("Enter a server host.");
                    return null;
                }
                if (!Int32.TryParse(serverPort.Text.Trim(), out port) || port < 1 || port > 65535)
                {
                    ShowInputWarning("Enter a port from 1 through 65535.");
                    return null;
                }

                request.ServerMode = ServerMode.Custom;
                request.ServerHost = host;
                request.ServerPort = port;
            }
            return request;
        }

        private void ApplyServerButton_Click(object sender, EventArgs e)
        {
            InstallRequest request = BuildServerRequest();
            if (request == null)
            {
                return;
            }
            if (request.ServerMode == ServerMode.Keep)
            {
                ShowInputWarning("Keep AIM's original server setting makes no change. Choose RealRetroLabz or a custom server to apply a setting.");
                return;
            }

            DialogResult answer = MessageBox.Show(
                "Close AIM first. Apply the selected server registry setting for AIM's next launch? Saving AIM's own Server settings dialog can overwrite it later.",
                "Apply AIM server setting",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Question);
            if (answer == DialogResult.Yes)
            {
                RunOperation(
                    new SetupOperation(OperationKind.ApplyServer, request),
                    "Working. Applying the selected server setting.");
            }
        }

        private void RestoreButton_Click(object sender, EventArgs e)
        {
            DialogResult answer = MessageBox.Show(
                "Restore the aimapi.dll file that this setup previously renamed? The AIM server setting will be left unchanged.",
                "Restore aimapi.dll",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Question);
            if (answer == DialogResult.Yes)
            {
                RunOperation(
                    new SetupOperation(OperationKind.Restore, null),
                    "Working. Restoring the tool-owned aimapi.dll change.");
            }
        }

        private void UninstallButton_Click(object sender, EventArgs e)
        {
            DialogResult answer = MessageBox.Show(
                "Close AIM first. Start AIM's normal registered uninstaller? This restores the tool-owned aimapi.dll rename first. The uninstaller can remove AIM and its user data according to the choices you make in its own window.",
                "Uninstall AIM",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Warning);
            if (answer == DialogResult.Yes)
            {
                RunOperation(
                    new SetupOperation(OperationKind.Uninstall, null),
                    "Working. Locating and starting AIM's normal uninstaller.");
            }
        }

        private void CloseButton_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void RunOperation(SetupOperation operation, string workingStatus)
        {
            operationRunning = true;
            SetControlsEnabled(false);
            status.ForeColor = SystemColors.ControlText;
            status.Text = workingStatus;
            details.Clear();
            downloadProgress.Value = 0;
            downloadProgress.Visible = false;
            lock (outputLock)
            {
                operationOutput.Length = 0;
            }
            operationWorker.RunWorkerAsync(operation);
        }

        private void OperationWorker_DoWork(object sender, DoWorkEventArgs e)
        {
            SetupOperation operation = (SetupOperation)e.Argument;
            if (operation.Kind == OperationKind.Install)
            {
                NativeWorkflow.Install(operation.InstallRequest, ReportStatusFromWorker, ReportDownloadProgressFromWorker);
            }
            else if (operation.Kind == OperationKind.Restore)
            {
                NativeWorkflow.Restore(ReportStatusFromWorker);
            }
            else if (operation.Kind == OperationKind.ApplyServer)
            {
                NativeWorkflow.ApplyServer(operation.InstallRequest, ReportStatusFromWorker);
            }
            else
            {
                NativeWorkflow.StartUninstall(ReportStatusFromWorker);
            }
            e.Result = operation.Kind;
        }

        private void ReportStatusFromWorker(string message)
        {
            string line = message + Environment.NewLine;
            lock (outputLock)
            {
                operationOutput.Append(line);
            }

            AppendOnUiThread(delegate
            {
                details.AppendText(line);
            });
        }

        private void ReportDownloadProgressFromWorker(int percent)
        {
            AppendOnUiThread(delegate
            {
                downloadProgress.Value = Math.Max(downloadProgress.Minimum, Math.Min(downloadProgress.Maximum, percent));
                downloadProgress.Visible = true;
                status.Text = "Downloading verified installer: " + percent + "%";
            });
        }

        private void AppendOnUiThread(MethodInvoker action)
        {
            if (IsDisposed || !IsHandleCreated)
            {
                return;
            }

            try
            {
                BeginInvoke(action);
            }
            catch (InvalidOperationException)
            {
                // The form is closing; the completed worker retains the outcome.
            }
        }

        private void OperationWorker_RunWorkerCompleted(object sender, RunWorkerCompletedEventArgs e)
        {
            PresentOperationCompletion(e);
        }

        private void PresentOperationCompletion(RunWorkerCompletedEventArgs e)
        {
            operationRunning = false;
            SetControlsEnabled(true);

            string output;
            lock (outputLock)
            {
                output = operationOutput.ToString().Trim();
            }

            if (e.Error != null)
            {
                string errorDetails = output.Length == 0 ? e.Error.Message : output + "\r\n\r\nERROR: " + e.Error.Message;
                if (details.TextLength == 0)
                {
                    details.Text = errorDetails;
                }
                else
                {
                    details.AppendText(Environment.NewLine + "ERROR: " + e.Error.Message + Environment.NewLine);
                }
                status.ForeColor = Color.Firebrick;
                status.Text = Program.ApplicationName + " failed.";
                MessageBox.Show(
                    Program.ApplicationName + " failed.\r\n\r\n" + TrimForDialog(errorDetails),
                    Program.ApplicationName + " failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return;
            }

            OperationKind completedOperation = (OperationKind)e.Result;
            if (details.TextLength == 0)
            {
                details.Text = output.Length == 0 ? "Completed without additional status text." : output;
            }
            status.ForeColor = Color.DarkGreen;
            string completionMessage;
            if (completedOperation == OperationKind.ApplyServer)
            {
                status.Text = "Server setting applied.";
                completionMessage = "AIM server setting applied. Start AIM afterwards.";
            }
            else if (completedOperation == OperationKind.Uninstall)
            {
                status.Text = "AIM uninstaller started.";
                completionMessage = "AIM's uninstaller was started. Complete it in its own window; this setup does not infer its result.";
            }
            else if (completedOperation == OperationKind.Restore)
            {
                status.Text = "aimapi.dll restored.";
                completionMessage = "aimapi.dll restore completed.";
            }
            else
            {
                status.Text = "Completed successfully.";
                completionMessage = Program.ApplicationName + " completed the AIM setup successfully.";
            }
            MessageBox.Show(
                completionMessage,
                completedOperation == OperationKind.Uninstall ? "AIM uninstaller" : Program.ApplicationName,
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
        }

        private void SetControlsEnabled(bool enabled)
        {
            downloadInstaller.Enabled = enabled;
            localInstaller.Enabled = enabled;
            installerPath.Enabled = enabled && localInstaller.Checked;
            browseButton.Enabled = enabled && localInstaller.Checked;
            removeAolDesktopShortcut.Enabled = enabled;
            realRetroLabz.Enabled = enabled;
            keepAIMDefault.Enabled = enabled;
            customServer.Enabled = enabled;
            serverHost.Enabled = enabled && customServer.Checked;
            serverPort.Enabled = enabled && customServer.Checked;
            installButton.Enabled = enabled;
            applyServerButton.Enabled = enabled;
            restoreButton.Enabled = enabled;
            uninstallButton.Enabled = enabled;
            closeButton.Enabled = enabled;
        }

        private void ShowInputWarning(string message)
        {
            MessageBox.Show(message, Program.ApplicationName, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private static string TrimForDialog(string text)
        {
            const int MaximumLength = 5000;
            return text.Length <= MaximumLength
                ? text
                : text.Substring(0, MaximumLength) + "\r\n\r\n(Additional status is shown in the setup window.)";
        }
    }
}
