using System.Diagnostics;
using System.Globalization;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Xml.Linq;

var builder = WebApplication.CreateBuilder(args);
builder.Configuration.AddEnvironmentVariables("LOCAL_TTS_");
var listenPort = builder.Configuration.GetValue("LocalTts:Port", 8000);
var bindHost = builder.Configuration.GetValue("LocalTts:BindHost", "0.0.0.0");
builder.WebHost.UseUrls($"http://{bindHost}:{listenPort}");
builder.Services.AddHttpClient();
builder.Services.AddSingleton<TtsOrchestrator>();

var app = builder.Build();
app.MapGet("/", (TtsOrchestrator tts) => Results.Json(tts.GetRoot()));
app.MapGet("/health", (TtsOrchestrator tts) => Results.Json(tts.GetHealth()));
app.MapGet("/v1/models", (TtsOrchestrator tts) => Results.Json(tts.GetModels()));
app.MapGet("/v1/audio/speech/files", (TtsOrchestrator tts) => Results.Json(tts.ListFiles()));
app.MapPost("/v1/audio/speech", async (SpeechRequest request, TtsOrchestrator tts, CancellationToken ct) =>
{
    var result = await tts.SynthesizeAsync(request, ct);
    if (request.ResponseMode?.Equals("json", StringComparison.OrdinalIgnoreCase) == true || request.SaveFile == true)
    {
        return Results.Json(result.Manifest);
    }

    return Results.File(result.Audio, result.ContentType, result.FileName);
});
app.Run();

public sealed record SpeechRequest(
    [property: JsonPropertyName("model")] string? Model,
    [property: JsonPropertyName("input")] string Input,
    [property: JsonPropertyName("voice")] string? Voice,
    [property: JsonPropertyName("response_format")] string? ResponseFormat,
    [property: JsonPropertyName("speed")] double? Speed,
    [property: JsonPropertyName("ssml")] bool? Ssml,
    [property: JsonPropertyName("cast")] Dictionary<string, string>? Cast,
    [property: JsonPropertyName("incremental")] bool? Incremental,
    [property: JsonPropertyName("save_file")] bool? SaveFile,
    [property: JsonPropertyName("response_mode")] string? ResponseMode,
    [property: JsonPropertyName("metadata")] Dictionary<string, string>? Metadata,
    [property: JsonPropertyName("input_format")] string? InputFormat);

public sealed class LocalTtsOptions
{
    public int Port { get; set; } = 8000;
    public string BindHost { get; set; } = "0.0.0.0";
    public string OutputDirectory { get; set; } = "tts-output";
    public string DefaultEngine { get; set; } = "kokoro";
    public string DefaultVoice { get; set; } = "narrator";
    public string DefaultFormat { get; set; } = "wav";
    public int Seed { get; set; } = 1701;
    public string LexiconPath { get; set; } = "lexicon.json";
    public string RenderPlatform { get; set; } = "platform-a-local-cpu";
    public bool AllowRemoteGpuEngines { get; set; }
    public bool IncrementalRendering { get; set; }
    public int ChunkSizeCharacters { get; set; } = 900;
    public bool SaveFiles { get; set; } = true;
    public Dictionary<string, string> EngineRedirects { get; set; } = new();
    public Dictionary<string, EngineOptions> Engines { get; set; } = new();
    public Dictionary<string, VoiceOptions> Voices { get; set; } = new();
}

public sealed class EngineOptions
{
    public string Type { get; set; } = "OpenAiCompatible";
    public string BaseUrl { get; set; } = "";
    public string? Model { get; set; }
    public int SampleRate { get; set; } = 24000;
    public Dictionary<string, string> Headers { get; set; } = new();
}

public sealed class VoiceOptions
{
    public string Engine { get; set; } = "kokoro";
    public string Speaker { get; set; } = "af_heart";
    public Dictionary<string, string> Parameters { get; set; } = new();
}

public sealed record ProxySpeechRequest([property: JsonPropertyName("model")] string Model, [property: JsonPropertyName("input")] string Input, [property: JsonPropertyName("voice")] string Voice, [property: JsonPropertyName("response_format")] string ResponseFormat, [property: JsonPropertyName("speed")] double Speed, [property: JsonPropertyName("seed")] int Seed, [property: JsonPropertyName("phoneme")] string? Phoneme);
public sealed record SpeechResult(byte[] Audio, string ContentType, string FileName, RenderManifest Manifest);
public sealed record RenderManifest(string Id, string? File, string FileName, string Format, string SsmlHash, int Seed, long RenderTimeMs, string RenditionHash, IReadOnlyList<SpanManifest> Spans, IReadOnlyList<string> Warnings, int Bytes);
public sealed record SpanManifest(string SpanHash, string AudioFileId, string? File, string VoiceId, string Engine, int Seed, long RenderTimeMs, string RenditionHash, bool CacheHit, string Kind, double Speed, double GainDb, int SilenceMs, string? SourceEngine, string? Phoneme);
public sealed record LexiconEntry(string? Phoneme, string? Alphabet, string? Alias, string? Note);

public sealed class TtsOrchestrator(IConfiguration configuration, IHttpClientFactory httpClientFactory)
{
    private readonly LocalTtsOptions _options = configuration.GetSection("LocalTts").Get<LocalTtsOptions>() ?? new();
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web) { DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull };

    public object GetRoot() => new { service = "local-tts-endpoint", status = "ok", platform = _options.RenderPlatform, listen_url = $"http://{_options.BindHost}:{_options.Port}", localhost_url = $"http://localhost:{_options.Port}", message = "Use GET /health, GET /v1/models, GET /v1/audio/speech/files, or POST /v1/audio/speech.", powershell = "Use curl.exe or Invoke-RestMethod; Windows PowerShell curl is an Invoke-WebRequest alias." };
    public object GetHealth() => new { status = "ok", service = "local-tts-endpoint", platform = _options.RenderPlatform, bind_host = _options.BindHost, port = _options.Port, listen_url = $"http://{_options.BindHost}:{_options.Port}", localhost_url = $"http://localhost:{_options.Port}", default_engine = _options.DefaultEngine, allow_remote_gpu_engines = _options.AllowRemoteGpuEngines, engines = _options.Engines.Keys };
    public object GetModels() => new { data = _options.Engines.Keys.Select(id => new { id, @object = "model", owned_by = "local" }) };

    public object ListFiles()
    {
        var dir = GetOutputDirectory();
        Directory.CreateDirectory(dir);
        return Directory.GetFiles(dir).OrderByDescending(File.GetCreationTimeUtc).Select(path => new FileInfo(path)).Select(f => new { f.Name, f.Length, created_utc = f.CreationTimeUtc });
    }

    public async Task<SpeechResult> SynthesizeAsync(SpeechRequest request, CancellationToken ct)
    {
        var timer = Stopwatch.StartNew();
        var format = NormalizeFormat(request.ResponseFormat ?? _options.DefaultFormat);
        var compiled = request.InputFormat?.Equals("palmcaster-dsl", StringComparison.OrdinalIgnoreCase) == true
            ? ToCompileResult(RenderPlanBuilder.FromPalmcaster(PalmcasterDslParser.Parse(request.Input), _options))
            : SsmlCompiler.Compile(request, _options);
        var spans = request.Incremental ?? _options.IncrementalRendering ? SplitSegments(compiled.Spans, Math.Max(120, _options.ChunkSizeCharacters)) : compiled.Spans;
        var rendered = new List<byte[]>();
        var spanManifests = new List<SpanManifest>();
        Directory.CreateDirectory(GetOutputDirectory());
        Directory.CreateDirectory(GetSpanDirectory());

        foreach (var span in spans)
        {
            var spanTimer = Stopwatch.StartNew();
            var resolved = ResolveSpan(span, request);
            var spanHash = Hash(JsonSerializer.Serialize(new { span, resolved.EngineName, resolved.Voice.Speaker, format, _options.Seed }));
            var audioFileId = $"span-{spanHash}";
            var spanFile = Path.Combine(GetSpanDirectory(), $"{audioFileId}.wav");
            byte[] audio;
            var cacheHit = File.Exists(spanFile);
            if (cacheHit)
            {
                audio = await File.ReadAllBytesAsync(spanFile, ct);
            }
            else
            {
                audio = span.Kind == SpanKind.Silence
                    ? Wav.Silence(TimeSpan.FromMilliseconds(span.SilenceMs), resolved.Engine.SampleRate)
                    : await RenderSpeechSpanAsync(span, resolved, request, format, ct);
                if (Math.Abs(span.GainDb) > 0.01) audio = Wav.ApplyGain(audio, span.GainDb);
                await File.WriteAllBytesAsync(spanFile, audio, ct);
            }

            rendered.Add(audio);
            spanTimer.Stop();
            spanManifests.Add(new SpanManifest(spanHash, audioFileId, spanFile, resolved.VoiceName, resolved.EngineName, _options.Seed, spanTimer.ElapsedMilliseconds, Hash(audio), cacheHit, span.Kind.ToString().ToLowerInvariant(), span.Speed, span.GainDb, span.SilenceMs, resolved.SourceEngineName, span.Phoneme));
        }

        var audioOut = rendered.Count == 1 ? rendered[0] : Wav.Concat(rendered);
        var id = Hash(request.Input + string.Join('|', spanManifests.Select(s => s.RenditionHash)))[..16];
        var fileName = $"speech-{id}.{format}";
        string? filePath = null;
        if (_options.SaveFiles || request.SaveFile == true)
        {
            filePath = Path.Combine(GetOutputDirectory(), fileName);
            await File.WriteAllBytesAsync(filePath, audioOut, ct);
        }

        timer.Stop();
        var manifest = new RenderManifest(id, filePath, fileName, format, Hash(request.Input), _options.Seed, timer.ElapsedMilliseconds, Hash(audioOut), spanManifests, compiled.Warnings, audioOut.Length);
        await File.WriteAllTextAsync(Path.Combine(GetOutputDirectory(), $"speech-{id}.manifest.json"), JsonSerializer.Serialize(manifest, JsonOptions), ct);
        return new SpeechResult(audioOut, ContentType(format), fileName, manifest);
    }

    private static CompileResult ToCompileResult(RenderPlan plan) => new(plan.Spans.ToList(), plan.Warnings.ToList());

    private async Task<byte[]> RenderSpeechSpanAsync(SpeechSpan span, ResolvedSpan resolved, SpeechRequest request, string format, CancellationToken ct)
    {
        if (resolved.Engine.Type.Equals("Silent", StringComparison.OrdinalIgnoreCase))
        {
            return Wav.Silence(TimeSpan.FromMilliseconds(Math.Clamp(span.Text.Length * 45 / span.Speed, 350, 60000)), resolved.Engine.SampleRate);
        }

        var client = httpClientFactory.CreateClient();
        foreach (var header in resolved.Engine.Headers) client.DefaultRequestHeaders.TryAddWithoutValidation(header.Key, header.Value);
        var payload = new ProxySpeechRequest(resolved.Engine.Model ?? resolved.EngineName, span.Phoneme is null ? span.Text : span.Phoneme, resolved.Voice.Speaker, format, span.Speed * (request.Speed ?? 1.0), _options.Seed, span.Phoneme);
        using var content = new StringContent(JsonSerializer.Serialize(payload, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await client.PostAsync(new Uri(new Uri(resolved.Engine.BaseUrl.TrimEnd('/') + "/"), "v1/audio/speech"), content, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsByteArrayAsync(ct);
    }

    private ResolvedSpan ResolveSpan(SpeechSpan span, SpeechRequest request)
    {
        var voiceName = span.Voice ?? request.Voice ?? _options.DefaultVoice;
        if (request.Cast is not null && request.Cast.TryGetValue(voiceName, out var mappedVoice)) voiceName = mappedVoice;
        _options.Voices.TryGetValue(voiceName, out var voice);
        voice ??= new VoiceOptions { Engine = request.Model ?? _options.DefaultEngine, Speaker = voiceName };
        var requestedEngineName = request.Model ?? voice.Engine ?? _options.DefaultEngine;
        var localCpuOnly = _options.RenderPlatform.Equals("platform-a-local-cpu", StringComparison.OrdinalIgnoreCase) || !_options.AllowRemoteGpuEngines;
        var engineName = (localCpuOnly && _options.EngineRedirects.TryGetValue(requestedEngineName, out var redirectedEngine)) ? redirectedEngine : requestedEngineName;
        _options.Engines.TryGetValue(engineName, out var engine);
        engine ??= _options.Engines.GetValueOrDefault(_options.DefaultEngine) ?? new EngineOptions();
        return new ResolvedSpan(voiceName, voice, engineName, engine, requestedEngineName == engineName ? null : requestedEngineName);
    }

    private static List<SpeechSpan> SplitSegments(List<SpeechSpan> source, int maxChars) => source.SelectMany(s => s.Kind == SpanKind.Silence ? new[] { s } : Enumerable.Range(0, Math.Max(1, (int)Math.Ceiling((double)s.Text.Length / maxChars))).Select(i => s with { Text = s.Text.Substring(i * maxChars, Math.Min(maxChars, s.Text.Length - i * maxChars)) })).Where(s => s.Kind == SpanKind.Silence || s.Text.Length > 0).ToList();
    private string GetOutputDirectory() => Path.GetFullPath(Environment.ExpandEnvironmentVariables(_options.OutputDirectory));
    private string GetSpanDirectory() => Path.Combine(GetOutputDirectory(), "spans");
    private static string NormalizeFormat(string format) => format.ToLowerInvariant() switch { "mp3" => "mp3", "opus" => "opus", "aac" => "aac", "flac" => "flac", _ => "wav" };
    private static string ContentType(string format) => format switch { "mp3" => "audio/mpeg", "opus" => "audio/opus", "aac" => "audio/aac", "flac" => "audio/flac", _ => "audio/wav" };
    private static string Hash(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
    private static string Hash(string text) => Hash(Encoding.UTF8.GetBytes(text));
}

public sealed record ResolvedSpan(string VoiceName, VoiceOptions Voice, string EngineName, EngineOptions Engine, string? SourceEngineName);
public enum SpanKind { Speech, Silence }
public sealed record SpeechSpan(SpanKind Kind, string Text, string? Voice, double Speed, double GainDb, string? Phoneme, int SilenceMs)
{
    public static SpeechSpan Speech(string text, string? voice, double speed = 1.0, double gainDb = 0, string? phoneme = null) => new(SpanKind.Speech, text, voice, speed, gainDb, phoneme, 0);
    public static SpeechSpan Silence(int ms) => new(SpanKind.Silence, string.Empty, null, 1.0, 0, null, ms);
}

public sealed record CompileState(string? Voice, double Speed, double GainDb);
public sealed record CompileResult(List<SpeechSpan> Spans, List<string> Warnings);

public static class SsmlCompiler
{
    public static CompileResult Compile(SpeechRequest request, LocalTtsOptions options)
    {
        var warnings = new List<string>();
        var lexicon = LoadLexicon(options);
        if (request.Ssml != true && !request.Input.TrimStart().StartsWith("<speak", StringComparison.OrdinalIgnoreCase))
        {
            return new CompileResult(new List<SpeechSpan> { SpeechSpan.Speech(NormalizeText(request.Input), request.Voice ?? options.DefaultVoice, request.Speed ?? 1.0) }, warnings);
        }

        try
        {
            var doc = XDocument.Parse(request.Input, LoadOptions.PreserveWhitespace);
            var spans = new List<SpeechSpan>();
            foreach (var node in doc.Root?.Nodes() ?? Enumerable.Empty<XNode>()) Lower(node, new CompileState(request.Voice ?? options.DefaultVoice, request.Speed ?? 1.0, 0), spans, warnings, lexicon);
            return new CompileResult(Coalesce(spans), warnings);
        }
        catch (Exception ex) when (ex is System.Xml.XmlException || ex is InvalidOperationException)
        {
            warnings.Add($"Invalid SSML fell back to plain text: {ex.Message}");
            return new CompileResult(new List<SpeechSpan> { SpeechSpan.Speech(NormalizeText(Regex.Replace(request.Input, "<.*?>", " ")), request.Voice ?? options.DefaultVoice, request.Speed ?? 1.0) }, warnings);
        }
    }

    private static void Lower(XNode node, CompileState state, List<SpeechSpan> spans, List<string> warnings, Dictionary<string, LexiconEntry> lexicon)
    {
        if (node is XText text)
        {
            AddSpeech(spans, text.Value, state, lexicon: lexicon);
            return;
        }
        if (node is not XElement e) return;
        var name = e.Name.LocalName.ToLowerInvariant();
        switch (name)
        {
            case "break":
                spans.Add(SpeechSpan.Silence(ParseDurationMs((string?)e.Attribute("time") ?? "250ms")));
                return;
            case "voice":
                LowerChildren(e, state with { Voice = (string?)e.Attribute("name") ?? state.Voice }, spans, warnings, lexicon);
                return;
            case "prosody":
                var next = state with { Speed = ClampRate((string?)e.Attribute("rate"), state.Speed, warnings), GainDb = state.GainDb + ParseVolumeDb((string?)e.Attribute("volume"), warnings) };
                if (e.Attribute("pitch") is not null) warnings.Add("prosody pitch is unsupported by the CPU assembly path and was dropped");
                LowerChildren(e, next, spans, warnings, lexicon);
                return;
            case "say-as":
                AddSpeech(spans, SayAs(e.Value, (string?)e.Attribute("interpret-as")), state, lexicon: lexicon);
                return;
            case "phoneme":
                AddSpeech(spans, NormalizeText(e.Value), state, phoneme: ConvertPhoneme((string?)e.Attribute("alphabet"), (string?)e.Attribute("ph"), warnings));
                return;
            case "sub":
                AddSpeech(spans, NormalizeText((string?)e.Attribute("alias") ?? e.Value), state, lexicon: lexicon);
                return;
            case "emphasis":
                spans.Add(SpeechSpan.Silence(80));
                LowerChildren(e, state with { Speed = Math.Max(0.75, state.Speed * 0.94), GainDb = state.GainDb + 1.0 }, spans, warnings, lexicon);
                spans.Add(SpeechSpan.Silence(80));
                warnings.Add("emphasis is approximate: slight rate reduction, small gain, and short pauses");
                return;
            default:
                warnings.Add($"unsupported SSML tag <{name}> degraded to inner text");
                LowerChildren(e, state, spans, warnings, lexicon);
                return;
        }
    }

    private static void LowerChildren(XElement e, CompileState state, List<SpeechSpan> spans, List<string> warnings, Dictionary<string, LexiconEntry> lexicon)
    {
        foreach (var child in e.Nodes()) Lower(child, state, spans, warnings, lexicon);
    }

    private static void AddSpeech(List<SpeechSpan> spans, string text, CompileState state, string? phoneme = null, Dictionary<string, LexiconEntry>? lexicon = null)
    {
        var normalized = NormalizeText(text);
        if (normalized.Length == 0) return;
        if (phoneme is not null || lexicon is null || lexicon.Count == 0)
        {
            spans.Add(SpeechSpan.Speech(normalized, state.Voice, state.Speed, state.GainDb, phoneme));
            return;
        }
        var cursor = 0;
        foreach (Match match in Regex.Matches(normalized, @"\b[\p{L}0-9'-]+\b"))
        {
            if (!lexicon.TryGetValue(match.Value, out var entry)) continue;
            if (match.Index > cursor) AddSpeech(spans, normalized[cursor..match.Index], state);
            spans.Add(SpeechSpan.Speech(entry.Alias ?? match.Value, state.Voice, state.Speed, state.GainDb, entry.Phoneme));
            cursor = match.Index + match.Length;
        }
        if (cursor < normalized.Length) AddSpeech(spans, normalized[cursor..], state);
    }

    private static Dictionary<string, LexiconEntry> LoadLexicon(LocalTtsOptions options)
    {
        var path = Path.IsPathRooted(options.LexiconPath) ? options.LexiconPath : Path.Combine(AppContext.BaseDirectory, options.LexiconPath);
        if (!File.Exists(path)) path = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", options.LexiconPath));
        if (!File.Exists(path)) path = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", options.LexiconPath));
        if (!File.Exists(path)) return new Dictionary<string, LexiconEntry>();
        return LexiconPrePass.Load(path);
    }
    private static List<SpeechSpan> Coalesce(List<SpeechSpan> spans) => spans.Where(s => s.Kind == SpanKind.Silence || s.Text.Length > 0).ToList();
    private static string NormalizeText(string text) => string.Join(' ', text.Split(default(string[]), StringSplitOptions.RemoveEmptyEntries));
    private static int ParseDurationMs(string value) => value.EndsWith("ms", StringComparison.OrdinalIgnoreCase) && int.TryParse(value[..^2], out var ms) ? Math.Clamp(ms, 0, 30000) : value.EndsWith('s') && double.TryParse(value[..^1], NumberStyles.Float, CultureInfo.InvariantCulture, out var sec) ? (int)Math.Clamp(sec * 1000, 0, 30000) : 250;
    private static double ClampRate(string? rate, double current, List<string> warnings)
    {
        if (string.IsNullOrWhiteSpace(rate)) return current;
        var mapped = rate.ToLowerInvariant() switch { "x-slow" => 0.6, "slow" => 0.8, "medium" => 1.0, "fast" => 1.2, "x-fast" => 1.4, _ => rate.EndsWith('%') && double.TryParse(rate[..^1], out var pct) ? pct / 100 : double.TryParse(rate, out var numeric) ? numeric : current };
        if (mapped < 0.5 || mapped > 1.6) warnings.Add($"prosody rate {rate} rejected as extreme; clamped");
        return Math.Clamp(mapped, 0.5, 1.6);
    }
    private static double ParseVolumeDb(string? volume, List<string> warnings)
    {
        if (string.IsNullOrWhiteSpace(volume)) return 0;
        var mapped = volume.ToLowerInvariant() switch { "silent" => -96, "x-soft" => -9, "soft" => -4, "medium" => 0, "loud" => 4, "x-loud" => 8, _ => volume.EndsWith("db", StringComparison.OrdinalIgnoreCase) && double.TryParse(volume[..^2], out var db) ? db : 0 };
        if (mapped is < -18 or > 9) warnings.Add($"prosody volume {volume} was clamped");
        return Math.Clamp(mapped, -18, 9);
    }
    private static string SayAs(string text, string? interpretAs) => interpretAs?.ToLowerInvariant() switch { "characters" => string.Join(' ', NormalizeText(text).ToCharArray()), "telephone" => string.Join(' ', Regex.Replace(text, "\\D", "").ToCharArray()), "ordinal" => ToOrdinal(text), "number" => Regex.Replace(text, "\\s+", " ").Trim(), "date" => text.Replace("/", " ").Replace("-", " "), "time" => text.Replace(":", " "), "currency" => text.Replace("$", " dollars ").Replace("€", " euros ").Replace("£", " pounds "), _ => NormalizeText(text) };
    private static string ToOrdinal(string text) => int.TryParse(Regex.Replace(text, "\\D", ""), out var n) ? $"{n}{((n % 100) is 11 or 12 or 13 ? "th" : (n % 10) switch { 1 => "st", 2 => "nd", 3 => "rd", _ => "th" })}" : NormalizeText(text);
    private static string? ConvertPhoneme(string? alphabet, string? ph, List<string> warnings)
    {
        if (string.IsNullOrWhiteSpace(ph)) return null;
        if (!string.Equals(alphabet, "ipa", StringComparison.OrdinalIgnoreCase)) warnings.Add($"phoneme alphabet {alphabet} passed through without conversion");
        return ph;
    }
}

public static class Wav
{
    public static byte[] Silence(TimeSpan duration, int sampleRate = 24000)
    {
        const short channels = 1;
        const short bits = 16;
        var sampleCount = (int)(duration.TotalSeconds * sampleRate);
        return WithHeader(new byte[sampleCount * channels * bits / 8], sampleRate, channels, bits);
    }

    public static byte[] Concat(IEnumerable<byte[]> wavs)
    {
        var list = wavs.ToList();
        var sampleRate = list.Count > 0 ? BitConverter.ToInt32(list[0], 24) : 24000;
        var pcm = list.SelectMany(w => w.Skip(44)).ToArray();
        return WithHeader(pcm, sampleRate, 1, 16);
    }

    public static byte[] ApplyGain(byte[] wav, double gainDb)
    {
        var output = wav.ToArray();
        var factor = Math.Pow(10, gainDb / 20);
        for (var i = 44; i + 1 < output.Length; i += 2)
        {
            var sample = BitConverter.ToInt16(output, i);
            var gained = (short)Math.Clamp(sample * factor, short.MinValue, short.MaxValue);
            var bytes = BitConverter.GetBytes(gained);
            output[i] = bytes[0]; output[i + 1] = bytes[1];
        }
        return output;
    }

    private static byte[] WithHeader(byte[] pcm, int sampleRate, short channels, short bits)
    {
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, Encoding.ASCII);
        var byteRate = sampleRate * channels * bits / 8;
        bw.Write("RIFF"u8.ToArray()); bw.Write(36 + pcm.Length); bw.Write("WAVEfmt "u8.ToArray());
        bw.Write(16); bw.Write((short)1); bw.Write(channels); bw.Write(sampleRate); bw.Write(byteRate); bw.Write((short)(channels * bits / 8)); bw.Write(bits);
        bw.Write("data"u8.ToArray()); bw.Write(pcm.Length); bw.Write(pcm);
        return ms.ToArray();
    }
}
