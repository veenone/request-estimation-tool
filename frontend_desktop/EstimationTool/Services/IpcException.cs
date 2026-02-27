namespace EstimationTool.Services;

/// <summary>
/// Represents an error that occurred during IPC communication with the Python backend.
/// </summary>
public class IpcException : Exception
{
    /// <summary>
    /// The IPC command that was being executed when the error occurred, if known.
    /// </summary>
    public string? Command { get; }

    /// <summary>
    /// The raw error payload returned by the Python process, if any.
    /// </summary>
    public string? RawResponse { get; }

    public IpcException(string message)
        : base(message)
    {
    }

    public IpcException(string message, string command)
        : base(message)
    {
        Command = command;
    }

    public IpcException(string message, string command, string rawResponse)
        : base(message)
    {
        Command = command;
        RawResponse = rawResponse;
    }

    public IpcException(string message, Exception innerException)
        : base(message, innerException)
    {
    }

    public IpcException(string message, string command, Exception innerException)
        : base(message, innerException)
    {
        Command = command;
    }

    public override string ToString()
    {
        var base_str = base.ToString();
        if (Command is not null)
            base_str = $"[Command: {Command}] {base_str}";
        if (RawResponse is not null)
            base_str += $"\nRaw response: {RawResponse}";
        return base_str;
    }
}
