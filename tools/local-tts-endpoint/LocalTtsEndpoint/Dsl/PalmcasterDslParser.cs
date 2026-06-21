using System.Text;
using System.Text.RegularExpressions;

public sealed record PalmcasterDocument(IReadOnlyList<PalmcasterBlock> Blocks, IReadOnlyList<string> Warnings)
{
    public string ToSsmlLikeText() => string.Join("\n", Blocks.Select(block => block.Text));
}

public sealed record PalmcasterBlock(int Level, string? Heading, string? Speaker, string Text, IReadOnlyDictionary<string, string> Tags);

public static class PalmcasterDslParser
{
    private static readonly Regex TagRegex = new(@"\{(?<name>speaker|lex|style):(?<value>[^{}]+)\}", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    public static PalmcasterDocument Parse(string input)
    {
        var warnings = new List<string>();
        var text = StripBom(input).Replace("\r\n", "\n");
        ValidateSingleStackTags(text, warnings);
        var blocks = new List<PalmcasterBlock>();
        string? speaker = null;
        var tags = new Dictionary<string, string>(StringComparer.Ordinal);
        var current = new StringBuilder();
        var currentLevel = 0;
        string? currentHeading = null;

        foreach (var rawLine in text.Split('\n'))
        {
            var line = rawLine.TrimEnd();
            var heading = Regex.Match(line, @"^(?<marks>#{1,6})\s+(?<title>.+)$");
            if (heading.Success)
            {
                Flush();
                currentLevel = heading.Groups["marks"].Value.Length;
                currentHeading = heading.Groups["title"].Value.Trim();
                continue;
            }

            var stripped = TagRegex.Replace(line, match =>
            {
                var name = match.Groups["name"].Value;
                var value = match.Groups["value"].Value.Trim();
                tags[name] = value;
                if (name == "speaker") speaker = value;
                if (name == "lex") return value;
                return string.Empty;
            });
            if (!string.IsNullOrWhiteSpace(stripped)) current.AppendLine(stripped.Trim());
        }
        Flush();
        return new PalmcasterDocument(blocks, warnings);

        void Flush()
        {
            var normalized = Normalize(current.ToString());
            if (normalized.Length > 0)
            {
                blocks.Add(new PalmcasterBlock(currentLevel, currentHeading, speaker, normalized, new Dictionary<string, string>(tags)));
            }
            current.Clear();
            tags.Clear();
        }
    }

    private static string StripBom(string input) => input.Length > 0 && input[0] == '\ufeff' ? input[1..] : input;
    private static string Normalize(string text) => string.Join(' ', text.Split(default(string[]), StringSplitOptions.RemoveEmptyEntries));

    private static void ValidateSingleStackTags(string text, List<string> warnings)
    {
        var balance = 0;
        foreach (var ch in text)
        {
            if (ch == '{') balance++;
            if (ch == '}') balance--;
            if (balance > 1) warnings.Add("nested DSL tags are not allowed; inner tag will be treated as text");
            if (balance < 0) { warnings.Add("unbalanced DSL closing brace found"); balance = 0; }
        }
        if (balance > 0) warnings.Add("unbalanced DSL opening brace found");
    }
}
