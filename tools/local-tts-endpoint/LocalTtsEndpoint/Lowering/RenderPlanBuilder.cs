public sealed record RenderPlan(IReadOnlyList<SpeechSpan> Spans, IReadOnlyList<string> Warnings);

public static class RenderPlanBuilder
{
    public static RenderPlan FromPalmcaster(PalmcasterDocument document, LocalTtsOptions options)
    {
        var spans = new List<SpeechSpan>();
        var warnings = document.Warnings.ToList();
        var lexicon = LexiconPrePass.Load(ResolvePath(options.LexiconPath));
        foreach (var block in document.Blocks)
        {
            var voice = block.Speaker ?? options.DefaultVoice;
            var speed = block.Tags.TryGetValue("style", out var style) && style.Contains("slow", StringComparison.OrdinalIgnoreCase) ? 0.92 : 1.0;
            spans.AddRange(LexiconPrePass.Apply(block.Text, new CompileState(voice, speed, 0), lexicon));
            if (block.Heading is not null) spans.Insert(Math.Max(0, spans.Count - 1), SpeechSpan.Silence(block.Level <= 1 ? 900 : 500));
        }
        return new RenderPlan(spans, warnings);
    }

    private static string ResolvePath(string path)
    {
        if (Path.IsPathRooted(path)) return path;
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, path),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", path)),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", path)),
        };
        return candidates.FirstOrDefault(File.Exists) ?? candidates[^1];
    }
}
