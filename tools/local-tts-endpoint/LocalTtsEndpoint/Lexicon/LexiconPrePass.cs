using System.Text.Json;
using System.Text.RegularExpressions;

public static class LexiconPrePass
{
    private static readonly HashSet<string> Excluded = new(StringComparer.Ordinal) { "SALT", "STAND", "THEM", "REM" };

    public static Dictionary<string, LexiconEntry> Load(string path)
    {
        if (!File.Exists(path)) return new Dictionary<string, LexiconEntry>(StringComparer.Ordinal);
        var entries = JsonSerializer.Deserialize<Dictionary<string, LexiconEntry>>(File.ReadAllText(path), new JsonSerializerOptions(JsonSerializerDefaults.Web)) ?? new();
        return entries.Where(kvp => !Excluded.Contains(kvp.Key)).ToDictionary(kvp => kvp.Key, kvp => kvp.Value, StringComparer.Ordinal);
    }

    public static IReadOnlyList<SpeechSpan> Apply(string text, CompileState state, Dictionary<string, LexiconEntry> lexicon)
    {
        var spans = new List<SpeechSpan>();
        var cursor = 0;
        foreach (Match match in Regex.Matches(text, @"\b[\p{L}0-9'-]+\b"))
        {
            if (!lexicon.TryGetValue(match.Value, out var entry)) continue;
            if (match.Index > cursor) AddPlain(spans, text[cursor..match.Index], state);
            spans.Add(SpeechSpan.Speech(entry.Alias ?? match.Value, state.Voice, state.Speed, state.GainDb, entry.Phoneme));
            cursor = match.Index + match.Length;
        }
        if (cursor < text.Length) AddPlain(spans, text[cursor..], state);
        if (spans.Count == 0) AddPlain(spans, text, state);
        return spans;
    }

    private static void AddPlain(List<SpeechSpan> spans, string text, CompileState state)
    {
        var normalized = string.Join(' ', text.Split(default(string[]), StringSplitOptions.RemoveEmptyEntries));
        if (normalized.Length > 0) spans.Add(SpeechSpan.Speech(normalized, state.Voice, state.Speed, state.GainDb));
    }
}
