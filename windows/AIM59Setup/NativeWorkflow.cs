using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using Microsoft.Win32;

namespace AIM59Setup
{
    internal enum InstallerSource
    {
        OldVersion,
        LocalFile
    }

    internal enum ServerMode
    {
        realretrolabz,
        Keep,
        Custom
    }

    internal sealed class InstallRequest
    {
        internal InstallerSource InstallerSource { get; set; }

        internal string InstallerPath { get; set; }

        internal ServerMode ServerMode { get; set; }

        internal string ServerHost { get; set; }

        internal int ServerPort { get; set; }

        internal bool RemoveAolDesktopShortcut { get; set; }
    }

    internal sealed class OldVersionDownloadForm
    {
        internal OldVersionDownloadForm(string action, string csrfToken)
        {
            Action = action;
            CsrfToken = csrfToken;
        }

        internal string Action { get; private set; }

        internal string CsrfToken { get; private set; }
    }

    internal sealed class UninstallerCommand
    {
        internal UninstallerCommand(string fileName, string arguments)
        {
            FileName = fileName;
            Arguments = arguments;
        }

        internal string FileName { get; private set; }

        internal string Arguments { get; private set; }
    }

    internal static class NativeWorkflow
    {
        internal const string DefaultServerHost = "aim.realretrolabz.com";
        internal const int DefaultServerPort = 5190;

        private const string InstallerPageUrl = "https://www.oldversion.com/software/aol-instant-messenger/aol-instant-messenger-5-9-3861/";
        private const string InstallerFileName = "aim593861.exe";
        private const long InstallerSize = 8715352;
        private const string InstallerSha256 = "018438bf22672ee119e864d78f838a538ed067bb76296957a00e0c1080979af1";
        private const string DisabledAimApiName = "aimapi.dll.aim59-disabled";
        private const string AolDesktopShortcutName = "Free AOL & Unlimited Internet.lnk";
        private const string AimRegistryServerKey = @"Software\America Online\AOL Instant Messenger (TM)\CurrentVersion\Server";
        private const string UninstallRegistryKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall";
        private const int InstallerCompletionTimeoutSeconds = 900;
        private const int InstallerCompletionPollMilliseconds = 2000;
        private const int InstallerFileSettleSeconds = 8;

        internal static void Install(
            InstallRequest request,
            Action<string> reportStatus,
            Action<int> reportDownloadProgress)
        {
            string installer = GetVerifiedInstaller(request, reportStatus, reportDownloadProgress);
            Report(reportStatus, "Starting the original AIM installer: " + installer);

            Process installerProcess = Process.Start(new ProcessStartInfo
            {
                FileName = installer,
                WorkingDirectory = Path.GetDirectoryName(installer),
                UseShellExecute = true
            });
            if (installerProcess == null)
            {
                throw new InvalidOperationException("The AIM installer could not be started.");
            }

            try
            {
                string aimDirectory = WaitForAimInstallation(installerProcess, reportStatus);
                StopAim();
                DisableAimApi(aimDirectory, reportStatus);
                ApplyServerChoice(request, reportStatus);
                if (request.RemoveAolDesktopShortcut)
                {
                    RemoveAolDesktopShortcut(reportStatus);
                }
                Report(reportStatus, "AIM 5.9.3861 is installed and patched. Launch: " + Path.Combine(aimDirectory, "aim.exe"));
            }
            finally
            {
                installerProcess.Dispose();
            }
        }

        internal static void Restore(Action<string> reportStatus)
        {
            string aimDirectory = FindAimDirectory();
            StopAim();
            RestoreAimApi(aimDirectory, reportStatus);
            Report(reportStatus, "AIM59 compatibility rollback completed. The AIM server preference was left unchanged.");
        }

        internal static void ApplyServer(InstallRequest request, Action<string> reportStatus)
        {
            RequireAimStopped("applying an AIM server setting");
            ApplyServerChoice(request, reportStatus);
            Report(reportStatus, "Server setting applied. Start AIM afterwards. Saving AIM's own Server settings dialog can overwrite this value.");
        }

        internal static void StartUninstall(Action<string> reportStatus)
        {
            RequireAimStopped("starting the AIM uninstaller");
            string aimDirectory = FindAimDirectory();
            UninstallerCommand command = FindAimUninstaller(aimDirectory, reportStatus);
            if (command == null)
            {
                throw new InvalidOperationException(
                    "AIM's uninstaller was not found in the registered uninstall entries under HKLM or HKCU. No uninstall was started and no AIM files were changed.");
            }

            RestoreAimApiForUninstall(aimDirectory, reportStatus);

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = command.FileName,
                Arguments = command.Arguments,
                UseShellExecute = true
            };
            if (Path.IsPathRooted(command.FileName))
            {
                startInfo.WorkingDirectory = Path.GetDirectoryName(command.FileName);
            }

            using (Process uninstallerProcess = Process.Start(startInfo))
            {
                if (uninstallerProcess == null)
                {
                    throw new InvalidOperationException("AIM's uninstaller could not be started.");
                }
            }
            Report(reportStatus, "AIM's normal uninstaller was started. Complete it in its own window; this setup does not infer its result.");
        }

        private static string GetVerifiedInstaller(
            InstallRequest request,
            Action<string> reportStatus,
            Action<int> reportDownloadProgress)
        {
            if (request.InstallerSource == InstallerSource.LocalFile)
            {
                if (String.IsNullOrWhiteSpace(request.InstallerPath))
                {
                    throw new InvalidOperationException("Choose the original AIM 5.9.3861 installer file.");
                }

                string localPath = Path.GetFullPath(request.InstallerPath);
                AssertInstallerIdentity(localPath);
                Report(reportStatus, "Using verified local installer: " + localPath);
                return localPath;
            }

            string cacheDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "rrlzAIM",
                "installers");
            string installerPath = Path.Combine(cacheDirectory, InstallerFileName);
            if (File.Exists(installerPath))
            {
                try
                {
                    AssertInstallerIdentity(installerPath);
                    Report(reportStatus, "Using verified cached installer: " + installerPath);
                    return installerPath;
                }
                catch (Exception)
                {
                    File.Delete(installerPath);
                }
            }

            Directory.CreateDirectory(cacheDirectory);
            string temporaryPath = installerPath + ".part";
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }

            try
            {
                ConfigureOldVersionTls(reportStatus);
                Report(reportStatus, "Getting the OldVersion download page.");
                CookieContainer cookies = new CookieContainer();
                string pageHtml = DownloadPage(cookies);
                OldVersionDownloadForm form = GetOldVersionDownloadForm(pageHtml);
                Uri downloadUri = new Uri(new Uri(InstallerPageUrl), form.Action);
                DownloadInstaller(downloadUri, form.CsrfToken, cookies, temporaryPath, reportStatus, reportDownloadProgress);
                File.Move(temporaryPath, installerPath);
                AssertInstallerIdentity(installerPath);
                return installerPath;
            }
            catch (Exception)
            {
                DeleteIfPresent(temporaryPath);
                DeleteIfPresent(installerPath);
                throw;
            }
        }

        private static string DownloadPage(CookieContainer cookies)
        {
            HttpWebRequest request = CreateRequest(new Uri(InstallerPageUrl), cookies);
            request.Method = "GET";
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (StreamReader reader = new StreamReader(response.GetResponseStream()))
            {
                return reader.ReadToEnd();
            }
        }

        private static OldVersionDownloadForm GetOldVersionDownloadForm(string html)
        {
            MatchCollection forms = Regex.Matches(
                html,
                "<form\\b(?<attributes>[^>]*)>(?<body>.*?)</form>",
                RegexOptions.IgnoreCase | RegexOptions.Singleline);
            foreach (Match form in forms)
            {
                string action = GetHtmlAttribute(form.Groups["attributes"].Value, "action");
                if (String.IsNullOrWhiteSpace(action)
                    || action.IndexOf("/software/download/", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    continue;
                }

                MatchCollection inputs = Regex.Matches(
                    form.Groups["body"].Value,
                    "<input\\b(?<attributes>[^>]*)>",
                    RegexOptions.IgnoreCase | RegexOptions.Singleline);
                foreach (Match input in inputs)
                {
                    string name = GetHtmlAttribute(input.Groups["attributes"].Value, "name");
                    if (!String.Equals(name, "csrfmiddlewaretoken", StringComparison.Ordinal))
                    {
                        continue;
                    }

                    string token = GetHtmlAttribute(input.Groups["attributes"].Value, "value");
                    if (!String.IsNullOrWhiteSpace(token))
                    {
                        return new OldVersionDownloadForm(action, token);
                    }
                }
            }

            throw new InvalidOperationException("OldVersion download form was not found; the site may have changed.");
        }

        private static string GetHtmlAttribute(string attributes, string name)
        {
            string pattern = "\\b" + Regex.Escape(name)
                + "\\s*=\\s*(?:\"(?<value>[^\"]*)\"|'(?<value>[^']*)'|(?<value>[^\\s>]+))";
            Match match = Regex.Match(attributes, pattern, RegexOptions.IgnoreCase | RegexOptions.Singleline);
            return match.Success ? WebUtility.HtmlDecode(match.Groups["value"].Value) : null;
        }

        private static void DownloadInstaller(
            Uri downloadUri,
            string csrfToken,
            CookieContainer cookies,
            string destinationPath,
            Action<string> reportStatus,
            Action<int> reportDownloadProgress)
        {
            byte[] requestBody = Encoding.UTF8.GetBytes(
                "csrfmiddlewaretoken=" + Uri.EscapeDataString(csrfToken));
            HttpWebRequest request = CreateRequest(downloadUri, cookies);
            request.Method = "POST";
            request.Referer = InstallerPageUrl;
            request.ContentType = "application/x-www-form-urlencoded";
            request.ContentLength = requestBody.Length;

            using (Stream requestStream = request.GetRequestStream())
            {
                requestStream.Write(requestBody, 0, requestBody.Length);
            }

            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (Stream responseStream = response.GetResponseStream())
            using (FileStream destination = new FileStream(destinationPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                byte[] buffer = new byte[65536];
                long downloadedBytes = 0;
                int nextStatusPercent = 0;
                int lastReportedPercent = -1;
                ReportDownloadProgress(reportStatus, reportDownloadProgress, 0, downloadedBytes);
                lastReportedPercent = 0;

                int read;
                while ((read = responseStream.Read(buffer, 0, buffer.Length)) > 0)
                {
                    destination.Write(buffer, 0, read);
                    downloadedBytes += read;
                    int percent = (int)Math.Min(100, (downloadedBytes * 100) / InstallerSize);
                    if (percent >= nextStatusPercent)
                    {
                        ReportDownloadProgress(reportStatus, reportDownloadProgress, percent, downloadedBytes);
                        lastReportedPercent = percent;
                        nextStatusPercent = percent + 5;
                    }
                }

                if (downloadedBytes == InstallerSize && lastReportedPercent < 100)
                {
                    ReportDownloadProgress(reportStatus, reportDownloadProgress, 100, downloadedBytes);
                }
                Report(reportStatus, String.Format(
                    CultureInfo.InvariantCulture,
                    "Download complete: {0} bytes. Verifying identity.",
                    downloadedBytes));
            }
        }

        private static HttpWebRequest CreateRequest(Uri uri, CookieContainer cookies)
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(uri);
            request.CookieContainer = cookies;
            request.UserAgent = "rrlzAIM/0.2";
            request.AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate;
            return request;
        }

        private static void ConfigureOldVersionTls(Action<string> reportStatus)
        {
            // A Mono-built assembly can otherwise inherit legacy .NET TLS
            // defaults when it is first run on Windows. OldVersion requires a
            // modern HTTPS handshake; do not enable obsolete protocol versions.
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            Report(reportStatus, "Connecting to OldVersion with TLS 1.2.");
        }

        private static void ReportDownloadProgress(
            Action<string> reportStatus,
            Action<int> reportDownloadProgress,
            int percent,
            long downloadedBytes)
        {
            if (reportDownloadProgress != null)
            {
                reportDownloadProgress(percent);
            }
            Report(reportStatus, String.Format(
                CultureInfo.InvariantCulture,
                "Download progress: {0}% ({1} of {2} bytes)",
                percent,
                downloadedBytes,
                InstallerSize));
        }

        private static void AssertInstallerIdentity(string path)
        {
            if (!File.Exists(path))
            {
                throw new FileNotFoundException("Installer was not found.", path);
            }

            FileInfo item = new FileInfo(path);
            if (item.Length != InstallerSize)
            {
                throw new InvalidOperationException(String.Format(
                    CultureInfo.InvariantCulture,
                    "Installer size mismatch: expected {0} bytes, got {1}.",
                    InstallerSize,
                    item.Length));
            }

            string actualHash;
            using (SHA256 sha256 = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
            {
                actualHash = ToLowerHex(sha256.ComputeHash(stream));
            }
            if (!String.Equals(actualHash, InstallerSha256, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Installer checksum mismatch: expected " + InstallerSha256 + ", got " + actualHash + ".");
            }
        }

        private static string WaitForAimInstallation(Process installerProcess, Action<string> reportStatus)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(InstallerCompletionTimeoutSeconds);
            DateTime nextStatus = DateTime.UtcNow;
            DateTime filesStableSince = DateTime.MinValue;
            string lastSignature = null;
            Exception lastDiscoveryError = null;

            while (DateTime.UtcNow < deadline)
            {
                if (installerProcess.HasExited && installerProcess.ExitCode != 0)
                {
                    throw new InvalidOperationException("AIM installer exited with code " + installerProcess.ExitCode + ".");
                }

                try
                {
                    string aimDirectory = FindAimDirectory();
                    FileInfo aimExe = new FileInfo(Path.Combine(aimDirectory, "aim.exe"));
                    FileInfo aimApi = new FileInfo(Path.Combine(aimDirectory, "aimapi.dll"));
                    if (!aimApi.Exists)
                    {
                        throw new FileNotFoundException("aimapi.dll was not found in " + aimDirectory, aimApi.FullName);
                    }

                    string signature = String.Format(
                        CultureInfo.InvariantCulture,
                        "{0}:{1}:{2}:{3}",
                        aimExe.Length,
                        aimExe.LastWriteTimeUtc.Ticks,
                        aimApi.Length,
                        aimApi.LastWriteTimeUtc.Ticks);
                    if (!String.Equals(signature, lastSignature, StringComparison.Ordinal))
                    {
                        lastSignature = signature;
                        filesStableSince = DateTime.UtcNow;
                    }
                    else if ((DateTime.UtcNow - filesStableSince).TotalSeconds >= InstallerFileSettleSeconds)
                    {
                        Report(reportStatus, "AIM installation files are stable. Applying compatibility changes.");
                        return aimDirectory;
                    }
                }
                catch (Exception error)
                {
                    lastDiscoveryError = error;
                    lastSignature = null;
                    filesStableSince = DateTime.MinValue;
                }

                if (DateTime.UtcNow >= nextStatus)
                {
                    Report(reportStatus, "Waiting for the AIM installer to create stable aim.exe and aimapi.dll files. The compatibility changes will run automatically afterwards.");
                    nextStatus = DateTime.UtcNow.AddSeconds(30);
                }
                Thread.Sleep(InstallerCompletionPollMilliseconds);
            }

            string reason = lastDiscoveryError == null ? "AIM was not found." : lastDiscoveryError.Message;
            throw new TimeoutException(
                "AIM installation was not detected within " + InstallerCompletionTimeoutSeconds + " seconds. " + reason);
        }

        private static string FindAimDirectory()
        {
            List<string> candidates = new List<string>();
            AddAimDirectoryCandidate(candidates, Environment.GetEnvironmentVariable("ProgramFiles(x86)"));
            AddAimDirectoryCandidate(candidates, Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles));

            List<string> matches = new List<string>();
            foreach (string candidate in candidates)
            {
                if (File.Exists(Path.Combine(candidate, "aim.exe")))
                {
                    matches.Add(candidate);
                }
            }

            if (matches.Count != 1)
            {
                throw new InvalidOperationException(
                    "Expected exactly one AIM directory containing aim.exe; found " + matches.Count + ".");
            }
            return matches[0];
        }

        private static void AddAimDirectoryCandidate(List<string> candidates, string programFiles)
        {
            if (String.IsNullOrWhiteSpace(programFiles))
            {
                return;
            }

            string candidate = Path.Combine(programFiles, "AIM");
            foreach (string existing in candidates)
            {
                if (String.Equals(existing, candidate, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
            }
            candidates.Add(candidate);
        }

        private static void StopAim()
        {
            foreach (Process process in Process.GetProcessesByName("aim"))
            {
                try
                {
                    process.Kill();
                    process.WaitForExit(10000);
                }
                catch (InvalidOperationException)
                {
                    // AIM exited between enumeration and termination.
                }
                finally
                {
                    process.Dispose();
                }
            }
        }

        private static void RequireAimStopped(string action)
        {
            bool isRunning = false;
            foreach (Process process in Process.GetProcessesByName("aim"))
            {
                isRunning = true;
                process.Dispose();
            }
            if (isRunning)
            {
                throw new InvalidOperationException("Close AIM before " + action + ".");
            }
        }

        private static void DisableAimApi(string aimDirectory, Action<string> reportStatus)
        {
            string original = Path.Combine(aimDirectory, "aimapi.dll");
            string disabled = Path.Combine(aimDirectory, DisabledAimApiName);
            if (File.Exists(original))
            {
                if (File.Exists(disabled))
                {
                    throw new InvalidOperationException(
                        "Both aimapi.dll and " + DisabledAimApiName + " exist. Resolve this manually; no file was changed.");
                }
                File.Move(original, disabled);
                Report(reportStatus, "Disabled: " + original);
                return;
            }

            if (File.Exists(disabled))
            {
                Report(reportStatus, "Already disabled: " + disabled);
                return;
            }

            throw new FileNotFoundException("aimapi.dll was not found in " + aimDirectory, original);
        }

        private static void RestoreAimApi(string aimDirectory, Action<string> reportStatus)
        {
            string original = Path.Combine(aimDirectory, "aimapi.dll");
            string disabled = Path.Combine(aimDirectory, DisabledAimApiName);
            if (File.Exists(original))
            {
                throw new InvalidOperationException("aimapi.dll already exists in " + aimDirectory + "; no file was changed.");
            }
            if (!File.Exists(disabled))
            {
                throw new FileNotFoundException("No AIM59-disabled aimapi.dll was found in " + aimDirectory, disabled);
            }

            File.Move(disabled, original);
            Report(reportStatus, "Restored: " + original);
        }

        private static void RestoreAimApiForUninstall(string aimDirectory, Action<string> reportStatus)
        {
            string original = Path.Combine(aimDirectory, "aimapi.dll");
            string disabled = Path.Combine(aimDirectory, DisabledAimApiName);
            if (File.Exists(original))
            {
                if (File.Exists(disabled))
                {
                    throw new InvalidOperationException(
                        "Both aimapi.dll and " + DisabledAimApiName + " exist. Resolve this manually before uninstalling; no file was changed.");
                }
                Report(reportStatus, "aimapi.dll is already restored for AIM's uninstaller.");
                return;
            }
            if (!File.Exists(disabled))
            {
                throw new FileNotFoundException(
                    "AIM's uninstaller requires aimapi.dll, but neither the original nor the tool-disabled file was found in " + aimDirectory,
                    original);
            }

            File.Move(disabled, original);
            Report(reportStatus, "Restored aimapi.dll before starting AIM's uninstaller: " + original);
        }

        private static void ApplyServerChoice(InstallRequest request, Action<string> reportStatus)
        {
            if (request.ServerMode == ServerMode.Keep)
            {
                Report(reportStatus, "Left the existing AIM server preference unchanged.");
                return;
            }

            string host = request.ServerMode == ServerMode.realretrolabz
                ? DefaultServerHost
                : request.ServerHost;
            int port = request.ServerMode == ServerMode.realretrolabz
                ? DefaultServerPort
                : request.ServerPort;
            if (String.IsNullOrWhiteSpace(host))
            {
                throw new InvalidOperationException("A custom AIM server host is required.");
            }
            if (port < 1 || port > 65535)
            {
                throw new InvalidOperationException("Server port must be a whole number from 1 through 65535.");
            }

            using (RegistryKey serverKey = Registry.CurrentUser.CreateSubKey(AimRegistryServerKey))
            {
                serverKey.SetValue("Host", host, RegistryValueKind.String);
                serverKey.SetValue("Port", port, RegistryValueKind.DWord);
            }
            Report(reportStatus, "Configured AIM server: " + host + ":" + port);
        }

        private static void RemoveAolDesktopShortcut(Action<string> reportStatus)
        {
            string[] desktopDirectories =
            {
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory)
            };
            List<string> checkedPaths = new List<string>();
            int removed = 0;
            foreach (string desktopDirectory in desktopDirectories)
            {
                if (String.IsNullOrWhiteSpace(desktopDirectory))
                {
                    continue;
                }

                string shortcutPath = Path.Combine(desktopDirectory, AolDesktopShortcutName);
                bool alreadyChecked = false;
                foreach (string existingPath in checkedPaths)
                {
                    if (String.Equals(existingPath, shortcutPath, StringComparison.OrdinalIgnoreCase))
                    {
                        alreadyChecked = true;
                        break;
                    }
                }
                if (alreadyChecked)
                {
                    continue;
                }
                checkedPaths.Add(shortcutPath);

                if (!File.Exists(shortcutPath))
                {
                    continue;
                }

                try
                {
                    File.Delete(shortcutPath);
                    removed++;
                    Report(reportStatus, "Removed optional AOL desktop shortcut: " + shortcutPath);
                }
                catch (Exception error)
                {
                    Report(reportStatus, "Could not remove optional AOL desktop shortcut " + shortcutPath + ": " + error.Message);
                }
            }

            if (removed == 0)
            {
                Report(reportStatus, "The optional AOL desktop shortcut was not present on the current or Public Desktop.");
            }
        }

        private static UninstallerCommand FindAimUninstaller(string aimDirectory, Action<string> reportStatus)
        {
            RegistryHive[] hives = { RegistryHive.LocalMachine, RegistryHive.CurrentUser };
            RegistryView[] views = { RegistryView.Registry32, RegistryView.Registry64 };
            Report(reportStatus, "Searching registered AIM uninstall entries in 32-bit and 64-bit HKLM/HKCU views.");
            foreach (RegistryHive hive in hives)
            {
                foreach (RegistryView view in views)
                {
                    using (RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view))
                    using (RegistryKey uninstallKey = baseKey.OpenSubKey(UninstallRegistryKey, false))
                    {
                        if (uninstallKey == null)
                        {
                            continue;
                        }

                        foreach (string entryName in uninstallKey.GetSubKeyNames())
                        {
                            using (RegistryKey entry = uninstallKey.OpenSubKey(entryName, false))
                            {
                                UninstallerCommand command = GetAimUninstallerCommand(entryName, entry, aimDirectory);
                                if (command != null)
                                {
                                    Report(reportStatus, "Found registered AIM uninstaller in " + hive + " " + view + ": " + entryName);
                                    return command;
                                }
                            }
                        }
                    }
                }
            }
            return null;
        }

        private static UninstallerCommand GetAimUninstallerCommand(
            string entryName,
            RegistryKey entry,
            string aimDirectory)
        {
            if (entry == null)
            {
                return null;
            }

            string displayName = Convert.ToString(entry.GetValue("DisplayName"));
            UninstallerCommand command = ParseUninstallerCommand(Convert.ToString(entry.GetValue("UninstallString")));
            if (command == null)
            {
                return null;
            }

            bool hasAimMarker = HasAimUninstallerMarker(displayName)
                || HasAimUninstallerMarker(entryName);
            bool commandIsInsideAimDirectory = Path.IsPathRooted(command.FileName)
                && IsPathWithinDirectory(command.FileName, aimDirectory);
            if (commandIsInsideAimDirectory)
            {
                return command;
            }

            string installLocation = Convert.ToString(entry.GetValue("InstallLocation"));
            if (hasAimMarker
                && !String.IsNullOrWhiteSpace(installLocation)
                && IsPathWithinDirectory(installLocation, aimDirectory))
            {
                return command;
            }
            return null;
        }

        private static bool HasAimUninstallerMarker(string value)
        {
            if (String.IsNullOrWhiteSpace(value))
            {
                return false;
            }

            if (value.IndexOf("AOL Instant Messenger", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return true;
            }

            return Regex.IsMatch(
                value,
                @"(?:^|[^A-Za-z0-9])AIM(?=$|[^A-Za-z0-9]|[0-9])",
                RegexOptions.IgnoreCase);
        }

        private static UninstallerCommand ParseUninstallerCommand(string commandLine)
        {
            if (String.IsNullOrWhiteSpace(commandLine))
            {
                return null;
            }

            string command = commandLine.Trim();
            string fileName;
            string arguments;
            if (command[0] == '"')
            {
                int closingQuote = command.IndexOf('"', 1);
                if (closingQuote <= 1)
                {
                    return null;
                }
                fileName = command.Substring(1, closingQuote - 1);
                arguments = command.Substring(closingQuote + 1).Trim();
            }
            else
            {
                Match executable = Regex.Match(
                    command,
                    @"^(?<file>.+?\.(?:exe|com))(?:\s+(?<arguments>.*))?$",
                    RegexOptions.IgnoreCase);
                if (!executable.Success)
                {
                    return null;
                }
                fileName = executable.Groups["file"].Value.Trim();
                arguments = executable.Groups["arguments"].Success
                    ? executable.Groups["arguments"].Value.Trim()
                    : String.Empty;
            }

            fileName = Environment.ExpandEnvironmentVariables(fileName);
            if (String.IsNullOrWhiteSpace(fileName)
                || (Path.IsPathRooted(fileName) && !File.Exists(fileName)))
            {
                return null;
            }
            return new UninstallerCommand(fileName, arguments);
        }

        private static bool IsPathWithinDirectory(string path, string directory)
        {
            try
            {
                string directoryPath = Path.GetFullPath(directory)
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string candidatePath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(path))
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                return String.Equals(candidatePath, directoryPath, StringComparison.OrdinalIgnoreCase)
                    || candidatePath.StartsWith(
                        directoryPath + Path.DirectorySeparatorChar,
                        StringComparison.OrdinalIgnoreCase)
                    || candidatePath.StartsWith(
                        directoryPath + Path.AltDirectorySeparatorChar,
                        StringComparison.OrdinalIgnoreCase);
            }
            catch (Exception)
            {
                return false;
            }
        }

        private static void Report(Action<string> reportStatus, string message)
        {
            if (reportStatus != null)
            {
                reportStatus(message);
            }
        }

        private static string ToLowerHex(byte[] bytes)
        {
            StringBuilder text = new StringBuilder(bytes.Length * 2);
            foreach (byte value in bytes)
            {
                text.Append(value.ToString("x2", CultureInfo.InvariantCulture));
            }
            return text.ToString();
        }

        private static void DeleteIfPresent(string path)
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }
}
