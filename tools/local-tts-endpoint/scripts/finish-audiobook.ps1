param(
  [Parameter(Mandatory=$true)][string]$InputDirectory,
  [string]$OutputDirectory = (Join-Path $InputDirectory 'finished'),
  [int]$DistributionSampleRate = 44100
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'ffmpeg is required for audiobook finishing.' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$chapterFiles = Get-ChildItem -Path $InputDirectory -Filter '*.wav' | Sort-Object Name
foreach ($chapter in $chapterFiles) {
  $out = Join-Path $OutputDirectory ($chapter.BaseName + '.m4a')
  ffmpeg -y -i $chapter.FullName -af "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,areverse,loudnorm=I=-19:TP=-3:LRA=11" -ar $DistributionSampleRate -c:a aac -b:a 128k $out
}
$list = Join-Path $OutputDirectory 'chapters.txt'
Get-ChildItem -Path $OutputDirectory -Filter '*.m4a' | Sort-Object Name | ForEach-Object { "file '$($_.FullName.Replace("'", "''"))'" } | Set-Content -Encoding UTF8 $list
ffmpeg -y -f concat -safe 0 -i $list -c copy (Join-Path $OutputDirectory 'audiobook.m4b')
