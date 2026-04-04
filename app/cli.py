"""CLI interface for ReWrite — AI Detector & Paraphraser."""

import argparse
import sys
import textwrap

from app.detection.ensemble import detect, detect_heuristic_only, detect_segments
from app.paraphrase.rewriter import paraphrase
from app.paraphrase.targeted import targeted_rewrite
from app.core.config import DEFAULT_MODEL


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "magenta": "\033[95m",
}


def c(text, color):
    return f"{COLORS[color]}{text}{COLORS['reset']}"


def score_color(score):
    if score >= 65:
        return "red"
    if score >= 40:
        return "yellow"
    return "green"


def print_bar(label, value, width=30):
    """Print a colored progress bar."""
    filled = int(value / 100 * width)
    color = score_color(value)
    bar = c("█" * filled, color) + c("░" * (width - filled), "dim")
    print(f"  {label:<24} {bar} {c(f'{value}%', color)}")


def print_header(text):
    print(f"\n{c('─' * 50, 'dim')}")
    print(f"  {c(text, 'bold')}")
    print(c("─" * 50, "dim"))


def read_input(args_text=None, file_path=None):
    """Read text from argument, file, or stdin."""
    if file_path:
        from app.document.parser import parse_file
        doc = parse_file(file_path)
        return doc.text

    if args_text:
        return args_text

    if not sys.stdin.isatty():
        return sys.stdin.read()

    print(c("\nPaste your text below (press Ctrl+D or Ctrl+Z when done):\n", "dim"))
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)


def cmd_detect(args):
    """Run the detector."""
    text = read_input(args.text, getattr(args, "file", None))
    if not text or not text.strip():
        print(c("Error: No text provided.", "red"))
        return

    if len(text.strip()) < 50:
        print(c("Error: Text too short — need at least 50 characters.", "red"))
        return

    print_header("AI DETECTION ANALYSIS")

    # Choose detection mode
    use_llm = not getattr(args, "fast", False)
    model = getattr(args, "model", DEFAULT_MODEL)

    if getattr(args, "segments", False):
        # Segment-level analysis
        seg_result = detect_segments(text, use_llm_judge=use_llm, model=model)

        score = seg_result["overall_score"]
        color = score_color(score)
        print(f"\n  {'Overall Score:':<24} {c(f'{score}%', color)} {c('AI likelihood', 'dim')}")
        print(f"  {'Verdict:':<24} {c(seg_result['overall_verdict'], color)}")
        print(f"  {'Segments:':<24} {len(seg_result['segments'])}\n")

        for i, seg in enumerate(seg_result["segments"]):
            seg_color = score_color(seg["score"])
            print(f"  {c(f'Segment {i + 1}:', 'bold')} {c(f'{seg[\"score\"]}%', seg_color)} — {c(seg['verdict'], seg_color)}")
            preview = seg["text"][:80] + "..." if len(seg["text"]) > 80 else seg["text"]
            print(f"    {c(preview, 'dim')}\n")

        # Generate PDF report if requested
        if getattr(args, "report", None):
            _generate_report(text, seg_result, args.report)
    else:
        result = detect(text, use_llm_judge=use_llm, model=model)

        score = result["score"]
        color = score_color(score)

        print(f"\n  {'Overall Score:':<24} {c(f'{score}%', color)} {c('AI likelihood', 'dim')}")
        print(f"  {'Verdict:':<24} {c(result['verdict'], color)}")

        if result.get("llm_reasoning"):
            print(f"  {'LLM Reasoning:':<24} {c(result['llm_reasoning'], 'dim')}")

        print(f"\n  {c('Feature Breakdown:', 'bold')}\n")
        labels = {
            "burstiness": "Burstiness",
            "vocabulary_markers": "AI Vocabulary",
            "type_token_ratio": "Lexical Diversity",
            "sentence_starters": "Sentence Starters",
            "paragraph_structure": "Paragraph Uniformity",
            "punctuation_diversity": "Punctuation Variety",
            "llm_judge": "LLM Judge",
        }
        for key, value in result["features"].items():
            print_bar(labels.get(key, key), value)

    print()


def cmd_paraphrase(args):
    """Run the paraphraser."""
    text = read_input(args.text, getattr(args, "file", None))
    if not text or not text.strip():
        print(c("Error: No text provided.", "red"))
        return

    intensity = args.intensity
    model = getattr(args, "model", DEFAULT_MODEL)
    domain = getattr(args, "domain", "general")

    print_header("PARAPHRASING")
    print(f"  Intensity: {c(intensity, 'cyan')}  |  Model: {c(model, 'cyan')}  |  Domain: {c(domain, 'cyan')}")
    print(f"  {c('Rewriting text... this may take a moment.', 'dim')}\n")

    if getattr(args, "targeted", False):
        result = targeted_rewrite(text, model=model, domain=domain)
        before = result["original_score"]
        after = result["final_score"]

        print_header("TARGETED REWRITE RESULTS")
        print(f"\n  Score: {c(f'{before}%', score_color(before))} → {c(f'{after}%', score_color(after))}")
        print(f"  Flagged: {result['flagged_count']} paragraphs  |  Rewritten: {result['rewritten_count']}")

        if result["needs_review"]:
            print(f"  {c(f'⚠ {len(result[\"needs_review\"])} paragraph(s) need manual review', 'yellow')}")
    else:
        result = paraphrase(
            text, intensity=intensity, model=model, domain=domain,
        )
        before = result["original_score"]
        after = result["final_score"]

        print_header("RESULTS")
        print(f"\n  Score: {c(f'{before}%', score_color(before))} → {c(f'{after}%', score_color(after))}  ({result['attempts']} pass{'es' if result['attempts'] > 1 else ''})")
        print(f"  Verdict: {c(result['final_verdict'], score_color(after))}")
        if result.get("similarity") and result["similarity"] < 1.0:
            print(f"  Similarity: {c(f'{result[\"similarity\"]:.1%}', 'cyan')}")

    print(f"\n  {c('Feature Breakdown:', 'bold')}\n")
    labels = {
        "burstiness": "Burstiness",
        "vocabulary_markers": "AI Vocabulary",
        "type_token_ratio": "Lexical Diversity",
        "sentence_starters": "Sentence Starters",
        "paragraph_structure": "Paragraph Uniformity",
        "punctuation_diversity": "Punctuation Variety",
    }
    features = result.get("final_features", {})
    for key, value in features.items():
        print_bar(labels.get(key, key), value)

    print_header("REWRITTEN TEXT")
    print()
    for paragraph in result["rewritten"].split("\n"):
        if paragraph.strip():
            wrapped = textwrap.fill(paragraph.strip(), width=78)
            print(f"  {wrapped}")
        else:
            print()
    print()

    if args.output:
        with open(args.output, "w") as f:
            f.write(result["rewritten"])
        print(c(f"  Output saved to {args.output}", "green"))
        print()


def _generate_report(text, seg_result, output_path):
    """Generate a PDF detection report."""
    from app.document.structure import Document
    from app.document.report import generate_report

    doc = Document.from_text(text)
    generate_report(
        document=doc,
        segment_scores=seg_result["segments"],
        overall_score=seg_result["overall_score"],
        overall_verdict=seg_result["overall_verdict"],
        output_path=output_path,
    )
    print(c(f"  Report saved to {output_path}", "green"))


def cmd_interactive(args):
    """Interactive mode — loop between detect and paraphrase."""
    print(c("\n  ReWrite — Interactive Mode", "bold"))
    print(c(f"  Model: {DEFAULT_MODEL}", "dim"))
    print(c("  Type 'detect', 'rewrite', or 'quit'\n", "dim"))

    while True:
        try:
            cmd = input(c("rewrite> ", "magenta")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if cmd in ("quit", "exit", "q"):
            break
        elif cmd in ("detect", "d", "scan"):
            print(c("  Paste text (Ctrl+D when done):", "dim"))
            lines = []
            try:
                while True:
                    lines.append(input())
            except EOFError:
                pass
            text = "\n".join(lines)
            if text.strip() and len(text.strip()) >= 50:
                args.text = text
                args.fast = False
                args.segments = False
                args.report = None
                args.model = DEFAULT_MODEL
                cmd_detect(args)
            else:
                print(c("  Need at least 50 characters.", "red"))
        elif cmd in ("rewrite", "r", "paraphrase", "p"):
            print(c("  Paste text (Ctrl+D when done):", "dim"))
            lines = []
            try:
                while True:
                    lines.append(input())
            except EOFError:
                pass
            text = "\n".join(lines)
            if text.strip():
                args.text = text
                args.intensity = input(c("  Intensity [light/medium/aggressive]: ", "dim")).strip() or "medium"
                args.domain = input(c("  Domain [general/cs/medicine/law/humanities]: ", "dim")).strip() or "general"
                args.targeted = False
                cmd_paraphrase(args)
            else:
                print(c("  No text provided.", "red"))
        elif cmd == "help":
            print("  detect  — Analyze text for AI signals")
            print("  rewrite — Paraphrase text to bypass detection")
            print("  quit    — Exit")
        else:
            print(c("  Unknown command. Type 'help' for options.", "dim"))


def main():
    parser = argparse.ArgumentParser(
        prog="rewrite",
        description="ReWrite — AI Text Detector & Paraphraser",
    )
    sub = parser.add_subparsers(dest="command")

    # detect
    p_detect = sub.add_parser("detect", help="Analyze text for AI-generated content")
    p_detect.add_argument("text", nargs="?", help="Text to analyze (or pipe via stdin)")
    p_detect.add_argument("-f", "--file", help="Path to PDF, DOCX, or TXT file")
    p_detect.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Model for LLM judge")
    p_detect.add_argument("--fast", action="store_true", help="Heuristics only (skip LLM judge)")
    p_detect.add_argument("--segments", action="store_true", help="Show per-segment scores")
    p_detect.add_argument("--report", help="Generate PDF report at this path")
    p_detect.set_defaults(func=cmd_detect)

    # paraphrase
    p_para = sub.add_parser("rewrite", help="Paraphrase text to bypass AI detection")
    p_para.add_argument("text", nargs="?", help="Text to rewrite (or pipe via stdin)")
    p_para.add_argument("-f", "--file", help="Path to PDF, DOCX, or TXT file")
    p_para.add_argument("-i", "--intensity", choices=["light", "medium", "aggressive"], default="medium")
    p_para.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Pollinations model ID")
    p_para.add_argument("-d", "--domain", choices=["general", "cs", "medicine", "law", "humanities"], default="general")
    p_para.add_argument("-o", "--output", help="Save output to file")
    p_para.add_argument("--targeted", action="store_true", help="Only rewrite flagged segments")
    p_para.set_defaults(func=cmd_paraphrase)

    # interactive
    p_inter = sub.add_parser("interactive", help="Interactive mode")
    p_inter.set_defaults(
        func=cmd_interactive, text=None, intensity="medium",
        model=DEFAULT_MODEL, output=None, domain="general",
    )

    args = parser.parse_args()
    if args.command is None:
        args.text = None
        args.intensity = "medium"
        args.model = DEFAULT_MODEL
        args.output = None
        args.domain = "general"
        cmd_interactive(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
