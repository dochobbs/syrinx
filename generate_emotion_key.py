#!/usr/bin/env python3
"""
Generate human-readable emotion answer keys from ground truth JSON files.

Produces a markdown report showing expected emotions per line, emotional arc,
and summary statistics — designed to compare against sentiment analysis tool output.
"""

import json
import os
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime


def ms_to_timestamp(ms: int) -> str:
  """Convert milliseconds to MM:SS format."""
  total_sec = ms / 1000
  minutes = int(total_sec // 60)
  seconds = int(total_sec % 60)
  return f"{minutes}:{seconds:02d}"


def generate_key(gt_path: str, output_dir: str = None) -> str:
  """Generate an emotion answer key markdown file from ground truth JSON."""
  with open(gt_path) as f:
    gt = json.load(f)

  encounter_id = gt["encounter_id"]
  audio_file = gt["audio_file"]
  duration_sec = gt["duration_sec"]
  lines = gt["lines"]

  # Collect stats
  emotions = Counter(l["emotion"] for l in lines)
  sentiments = Counter(l["coarse_sentiment"] for l in lines)
  speakers = Counter(l["speaker"] for l in lines)

  # Build markdown
  md = []
  md.append(f"# Emotion Answer Key: {encounter_id}")
  md.append("")
  md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
  md.append(f"**Audio File:** `{audio_file}`")
  md.append(f"**Duration:** {duration_sec}s ({duration_sec/60:.1f} min)")
  md.append(f"**Total Lines:** {len(lines)}")
  md.append("")

  # Summary stats
  md.append("## Summary")
  md.append("")
  md.append("### Sentiment Distribution")
  md.append("")
  md.append("| Sentiment | Count | % |")
  md.append("|-----------|-------|---|")
  for s, c in sentiments.most_common():
    pct = 100 * c / len(lines)
    md.append(f"| {s} | {c} | {pct:.0f}% |")
  md.append("")

  md.append("### Emotion Distribution")
  md.append("")
  md.append("| Emotion | Count | % |")
  md.append("|---------|-------|---|")
  for e, c in emotions.most_common():
    pct = 100 * c / len(lines)
    md.append(f"| {e} | {c} | {pct:.0f}% |")
  md.append("")

  md.append("### Speaker Breakdown")
  md.append("")
  md.append("| Speaker | Lines |")
  md.append("|---------|-------|")
  for sp, c in speakers.most_common():
    md.append(f"| {sp} | {c} |")
  md.append("")

  # Per-speaker emotion profile
  md.append("### Per-Speaker Emotion Profile")
  md.append("")
  for sp in speakers:
    sp_emotions = Counter(l["emotion"] for l in lines if l["speaker"] == sp)
    sp_sentiments = Counter(l["coarse_sentiment"] for l in lines if l["speaker"] == sp)
    sp_total = speakers[sp]
    emotion_str = ", ".join(f"{e} ({c})" for e, c in sp_emotions.most_common())
    sentiment_str = ", ".join(f"{s} ({c})" for s, c in sp_sentiments.most_common())
    md.append(f"**{sp}** ({sp_total} lines): {emotion_str}")
    md.append(f"  Sentiment: {sentiment_str}")
    md.append("")

  # Emotional arc
  md.append("## Emotional Arc")
  md.append("")
  md.append("Visual representation of sentiment flow across the encounter:")
  md.append("")
  sentiment_icons = {"negative": "🔴", "neutral": "⚪", "positive": "🟢"}
  for line in lines:
    icon = sentiment_icons.get(line["coarse_sentiment"], "⚪")
    ts = ms_to_timestamp(line["approx_start_ms"])
    md.append(
      f"  {line['index']+1:2d}. {icon} `{ts}` "
      f"**{line['speaker']}** — {line['emotion']} "
      f"({line['coarse_sentiment']})"
    )
  md.append("")

  # Detailed line-by-line key
  md.append("## Line-by-Line Detail")
  md.append("")
  md.append("| # | Time | Speaker | Emotion | Sentiment | Stability | Style | Text (truncated) |")
  md.append("|---|------|---------|---------|-----------|-----------|-------|-----------------|")
  for line in lines:
    ts = ms_to_timestamp(line["approx_start_ms"])
    text = line["text"][:60] + "..." if len(line["text"]) > 60 else line["text"]
    stab = line["voice_params"]["stability"]
    style = line["voice_params"]["style"]
    md.append(
      f"| {line['index']+1} | {ts} | {line['speaker']} | "
      f"{line['emotion']} | {line['coarse_sentiment']} | "
      f"{stab} | {style} | {text} |"
    )
  md.append("")

  # Voice parameter ranges
  md.append("## Voice Parameter Ranges Used")
  md.append("")
  stabilities = [l["voice_params"]["stability"] for l in lines]
  styles = [l["voice_params"]["style"] for l in lines]
  md.append(f"- **Stability:** {min(stabilities):.2f} – {max(stabilities):.2f}")
  md.append(f"- **Style:** {min(styles):.2f} – {max(styles):.2f}")
  md.append("")

  content = "\n".join(md)

  # Write output
  out_dir = output_dir or os.path.dirname(gt_path)
  key_filename = f"{encounter_id}_emotion_key.md"
  key_path = os.path.join(out_dir, key_filename)
  with open(key_path, "w") as f:
    f.write(content)

  return key_path


def main():
  parser = argparse.ArgumentParser(
    description="Generate emotion answer keys from ground truth JSON"
  )
  parser.add_argument(
    "ground_truth",
    nargs="?",
    help="Path to a single ground truth JSON file"
  )
  parser.add_argument(
    "--all", "-a",
    action="store_true",
    help="Generate keys for all ground truth files in audio_output/"
  )
  parser.add_argument(
    "--output-dir", "-o",
    default=None,
    help="Output directory (default: same as ground truth file)"
  )

  args = parser.parse_args()

  if not args.ground_truth and not args.all:
    parser.print_help()
    return 1

  gt_files = []
  if args.all:
    gt_dir = Path("audio_output")
    gt_files = sorted(gt_dir.glob("*_ground_truth.json"))
    if not gt_files:
      print("No ground truth files found in audio_output/")
      return 1
  else:
    gt_files = [Path(args.ground_truth)]

  for gt_file in gt_files:
    key_path = generate_key(str(gt_file), args.output_dir)
    print(f"  {gt_file.name} -> {os.path.basename(key_path)}")

  print(f"\nGenerated {len(gt_files)} emotion key(s)")
  return 0


if __name__ == "__main__":
  exit(main())
