using System.Text.Json;
using EstimationTool.Forms;
using EstimationTool.Services;

namespace EstimationTool;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        var backendUrl = ReadBackendUrl();

        // Allow override via command-line argument
        if (args.Length > 0)
            backendUrl = args[0];

        var apiService = new BackendApiService(backendUrl);

        Application.ApplicationExit += (s, e) => apiService.Dispose();

        Application.Run(new MainForm(apiService));
    }

    private static string ReadBackendUrl()
    {
        try
        {
            var settingsPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "appsettings.json");

            // Walk up to find appsettings.json (supports dev and installed layouts)
            var dir = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 6; i++)
            {
                var candidate = Path.Combine(dir, "appsettings.json");
                if (File.Exists(candidate))
                {
                    settingsPath = candidate;
                    break;
                }
                var parent = Directory.GetParent(dir);
                if (parent == null) break;
                dir = parent.FullName;
            }

            if (File.Exists(settingsPath))
            {
                var json = File.ReadAllText(settingsPath);
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("BackendUrl", out var prop))
                    return prop.GetString() ?? "http://localhost:8000";
            }
        }
        catch
        {
            // Fall through to default
        }

        return "http://localhost:8000";
    }
}
