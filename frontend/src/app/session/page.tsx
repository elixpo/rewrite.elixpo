"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { startLogin } from "@/lib/auth";
import { getAllPaperSessions, deletePaperSession, type PaperSession } from "@/lib/paperSession";
import { ScoreBadge, ScoreBar } from "@/components/ScoreBadge";
import { detectText } from "@/lib/api";
import type { DetectResult } from "@/lib/api";

const DOMAIN_LABELS: Record<string, string> = {
  general: "General",
  cs: "Computer Science",
  medicine: "Medicine",
  law: "Law",
  humanities: "Humanities",
};

export default function SessionPage() {
  const { loggedIn } = useAuth();
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  const [mounted, setMounted] = useState(false);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  useEffect(() => {
    setSessions(getAllPaperSessions());
    setMounted(true);
  }, []);

  const handleDelete = (slug: string) => {
    deletePaperSession(slug);
    setSessions((prev) => prev.filter((s) => s.slug !== slug));
    if (selectedSlug === slug) setSelectedSlug(null);
  };

  if (!loggedIn) {
    return (
      <div className="max-w-3xl mx-auto px-6 text-center py-20 space-y-4">
        <h1 className="text-2xl font-bold font-display text-text-primary">Sessions</h1>
        <p className="text-text-muted text-sm">Sign in to view your session history and resume jobs.</p>
        <button onClick={startLogin} className="btn-primary px-5 py-2 rounded-lg text-sm">Sign in</button>
      </div>
    );
  }

  if (!mounted) return null;

  const selectedSession = sessions.find((s) => s.slug === selectedSlug) || null;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-display text-text-primary">Sessions</h1>
          <p className="text-text-muted text-xs mt-1">{sessions.length} paper{sessions.length !== 1 ? "s" : ""} in this browser session</p>
        </div>
        <Link href="/" className="btn-primary px-4 py-1.5 rounded-lg text-xs">
          New paper
        </Link>
      </div>

      {sessions.length === 0 ? (
        <div className="glass-card p-12 text-center space-y-3">
          <div className="text-4xl opacity-30">📄</div>
          <p className="text-text-muted text-sm">No sessions yet</p>
          <p className="text-text-subtle text-xs">Upload or paste a .tex file from the <Link href="/" className="text-lime underline">home page</Link> to get started</p>
        </div>
      ) : (
        <div className="flex gap-5">
          {/* Session list */}
          <div className={`space-y-3 shrink-0 ${selectedSession ? "w-72" : "flex-1"}`}>
            <div className={selectedSession ? "space-y-2" : "grid gap-3 sm:grid-cols-2"}>
              {sessions.map((s) => (
                <SessionCard
                  key={s.slug}
                  session={s}
                  selected={s.slug === selectedSlug}
                  compact={!!selectedSession}
                  onSelect={() => setSelectedSlug(s.slug === selectedSlug ? null : s.slug)}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          </div>

          {/* Detail panel */}
          {selectedSession && (
            <div className="flex-1 min-w-0">
              <SessionDetail session={selectedSession} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SessionCard({
  session, selected, compact, onSelect, onDelete,
}: {
  session: PaperSession;
  selected: boolean;
  compact: boolean;
  onSelect: () => void;
  onDelete: (slug: string) => void;
}) {
  const wordCount = session.tex.trim().split(/\s+/).filter(Boolean).length;
  const lineCount = session.tex.split("\n").length;
  const preview = extractPreview(session.tex);
  const timeAgo = formatTimeAgo(session.createdAt);

  return (
    <div
      onClick={onSelect}
      className={`glass-card p-4 cursor-pointer group transition-all ${
        selected ? "border-lime-border bg-lime-dim" : "hover:border-border-hover"
      } ${compact ? "space-y-1" : "space-y-3"}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className={`font-semibold text-text-primary truncate ${compact ? "text-xs" : "text-sm"} ${selected ? "text-lime" : "group-hover:text-lime"} transition-colors`}>
            {session.filename || `Paper ${session.slug.slice(0, 6)}`}
          </h3>
          <p className="text-text-subtle text-[10px] mt-0.5">{timeAgo}</p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(session.slug); }}
          className="text-text-subtle hover:text-error transition-colors p-1 shrink-0 opacity-0 group-hover:opacity-100"
          title="Delete"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {!compact && <p className="text-text-muted text-xs leading-relaxed line-clamp-3">{preview}</p>}

      <div className="flex items-center gap-3 text-[10px] text-text-subtle">
        <span>{lineCount} lines</span>
        <span>{wordCount.toLocaleString()} words</span>
        <span className="px-1.5 py-0.5 rounded bg-bg-glass border border-border-light">
          {DOMAIN_LABELS[session.domain] || session.domain}
        </span>
      </div>
    </div>
  );
}

function SessionDetail({ session }: { session: PaperSession }) {
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wordCount = session.tex.trim().split(/\s+/).filter(Boolean).length;
  const lineCount = session.tex.split("\n").length;
  const preview = extractPreview(session.tex);

  const handleRunDetect = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await detectText(session.tex, true);
      setDetectResult(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Reset when session changes
  useEffect(() => {
    setDetectResult(null);
    setError(null);
  }, [session.slug]);

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-border-light">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold font-display text-text-primary">
            {session.filename || `Paper ${session.slug.slice(0, 6)}`}
          </h2>
          <Link href={`/paper/${session.slug}`} className="btn-primary px-3 py-1 rounded-lg text-xs">
            Open in editor
          </Link>
        </div>
        <div className="flex items-center gap-4 text-xs text-text-muted">
          <span>{lineCount} lines</span>
          <span>{wordCount.toLocaleString()} words</span>
          <span className="px-1.5 py-0.5 rounded bg-bg-glass border border-border-light text-[10px]">
            {DOMAIN_LABELS[session.domain] || session.domain}
          </span>
          <span>{formatTimeAgo(session.createdAt)}</span>
        </div>
      </div>

      {/* Preview */}
      <div className="p-5 border-b border-border-light">
        <p className="text-[10px] text-text-muted uppercase tracking-wider font-semibold mb-2">Preview</p>
        <div className="bg-editor-bg rounded-lg p-3 max-h-40 overflow-y-auto">
          <pre className="text-text-secondary text-xs font-mono whitespace-pre-wrap leading-relaxed">
            {session.tex.slice(0, 1500)}{session.tex.length > 1500 ? "\n..." : ""}
          </pre>
        </div>
      </div>

      {/* Detection */}
      <div className="p-5">
        {!detectResult && !loading && (
          <div className="text-center space-y-3">
            <p className="text-text-muted text-xs">Run a quick AI detection scan on this paper</p>
            <button onClick={handleRunDetect} className="btn-primary px-5 py-2 rounded-lg text-xs">
              Check AI %
            </button>
          </div>
        )}

        {loading && (
          <div className="text-center space-y-3 py-4">
            <div className="w-5 h-5 mx-auto rounded-full border-2 border-lime border-t-transparent animate-spin" />
            <p className="text-text-muted text-xs">Analyzing...</p>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.25)]">
            <p className="text-error text-xs">{error}</p>
          </div>
        )}

        {detectResult && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold font-display text-text-primary">Detection Results</h3>
              <ScoreBadge score={detectResult.score} size="lg" />
            </div>
            <p className="text-text-muted text-xs">{detectResult.verdict}</p>

            {/* Feature bars */}
            <div className="space-y-1.5">
              {Object.entries(detectResult.features)
                .filter(([, v]) => v > 0)
                .sort(([, a], [, b]) => b - a)
                .map(([key, value]) => (
                  <ScoreBar key={key} label={formatFeature(key)} score={value} />
                ))}
            </div>

            {/* Segments */}
            {detectResult.segments.length > 0 && (
              <div className="space-y-1.5 pt-3 border-t border-border-light">
                <p className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">Per-paragraph</p>
                <div className="max-h-60 overflow-y-auto space-y-1">
                  {detectResult.segments.map((seg) => (
                    <div key={seg.index} className="flex items-start gap-2 text-xs py-1.5 px-2 rounded hover:bg-bg-glass">
                      <ScoreBadge score={seg.score} size="sm" />
                      <p className="text-text-muted text-[11px] leading-snug line-clamp-2 flex-1">{seg.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-2">
              <Link href={`/paper/${session.slug}`} className="btn-primary px-3 py-1.5 rounded-lg text-xs">
                Open in editor
              </Link>
              <button onClick={handleRunDetect} className="btn-ghost px-3 py-1.5 rounded-lg text-xs">
                Re-scan
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function extractPreview(tex: string): string {
  const lines = tex.split("\n");
  const prose: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("\\") || trimmed.startsWith("%") || trimmed.startsWith("{") || trimmed.startsWith("}")) continue;
    const clean = trimmed
      .replace(/\\[a-zA-Z]+\*?(\{[^}]*\})*(\[[^\]]*\])*/g, "")
      .replace(/[{}$\\]/g, "")
      .trim();
    if (clean.length > 10) prose.push(clean);
    if (prose.join(" ").length > 200) break;
  }
  return prose.join(" ").slice(0, 200) || "LaTeX document";
}

function formatTimeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatFeature(key: string): string {
  const labels: Record<string, string> = {
    burstiness: "Burstiness", vocabulary_markers: "AI Vocabulary",
    paragraph_structure: "Paragraph Uniformity", n_gram_uniformity: "N-gram Uniformity",
    repetition: "Repetition", punctuation_diversity: "Punctuation Variety",
    perplexity: "Perplexity", coherence: "Coherence", readability: "Readability",
    entropy: "Entropy", type_token_ratio: "Lexical Diversity",
    sentence_starters: "Sentence Starters", llm_judge: "LLM Judge",
  };
  return labels[key] || key;
}
