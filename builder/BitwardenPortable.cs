using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

// Independent community launcher: runs the OFFICIAL, UNMODIFIED Bitwarden portable EXE.
// Does not store credentials, inspect Bitwarden files, or change Windows registry/PATH.
internal static class BitwardenPortable
{
    private static string Quote(string text)
    {
        if (text.Length > 0 && text.IndexOfAny(new char[] { ' ', '\t', '\n', '"' }) < 0)
            return text;
        StringBuilder builder = new StringBuilder("\"");
        int backslashes = 0;
        foreach (char c in text)
        {
            if (c == '\\') { backslashes++; continue; }
            if (c == '"') { builder.Append('\\', backslashes * 2 + 1); builder.Append('"'); backslashes = 0; continue; }
            builder.Append('\\', backslashes); backslashes = 0; builder.Append(c);
        }
        builder.Append('\\', backslashes * 2);
        builder.Append('"');
        return builder.ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string applicationDir = Path.Combine(root, @"App\Bitwarden");
        string officialExecutable = Path.Combine(applicationDir, "Bitwarden-Portable.exe");
        string appData = Path.Combine(root, @"Data\Bitwarden");
        try
        {
            if (!File.Exists(officialExecutable))
            {
                MessageBox.Show("The official portable Bitwarden executable is missing. Extract the entire package.",
                    "Bitwarden Portable", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }
            Directory.CreateDirectory(appData);
            // Bitwarden's documented absolute-path override, passed only to the child.
            ProcessStartInfo start = new ProcessStartInfo(officialExecutable);
            start.UseShellExecute = false;
            start.WorkingDirectory = applicationDir;
            start.EnvironmentVariables["BITWARDEN_APPDATA_DIR"] = appData;
            // Electron portable applications use TEMP for unpacking. Keeping the cache
            // within Data avoids pointing their temporary extraction to AppData.
            string temporary = Path.Combine(root, @"Data\Temp");
            Directory.CreateDirectory(temporary);
            start.EnvironmentVariables["TEMP"] = temporary;
            start.EnvironmentVariables["TMP"] = temporary;
            StringBuilder arguments = new StringBuilder();
            foreach (string argument in args)
            {
                if (arguments.Length > 0) arguments.Append(' ');
                arguments.Append(Quote(argument));
            }
            start.Arguments = arguments.ToString();
            using (Process process = Process.Start(start))
            {
                if (process == null) return 3;
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show("Could not start Bitwarden Portable:\n" + ex.Message,
                "Bitwarden Portable", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        // Do not automatically delete Data or TEMP: vault/state could still be in use.
    }
}
