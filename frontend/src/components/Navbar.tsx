"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/AuthContext";
import { startLogin } from "@/lib/auth";
import { getLimits, getPlan } from "@/lib/plans";
import { getGuestUsageToday } from "@/lib/api";

export function Navbar() {
  const { user, loggedIn, loading, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const plan = getPlan(loggedIn, false);
  const limits = getLimits(loggedIn, false);
  const checksUsed = getGuestUsageToday(); // works for all tiers

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Generate initials from displayName
  const initials = user?.displayName
    ? user.displayName
        .split(/[\s-]+/)
        .map((w) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  return (
    <nav className="border-b border-border-light">
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
        <a href="/" className="text-lg font-bold font-display text-gradient">
          ReWrite
        </a>

        <div className="flex items-center gap-4 text-xs">
          <a href="/pricing" className="text-text-muted hover:text-text-primary transition-colors">
            Pricing
          </a>

          {loading ? (
            <span className="w-8 h-8 rounded-full bg-bg-glass animate-pulse" />
          ) : user ? (
            <div ref={menuRef} className="relative">
              {/* Avatar button */}
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="w-8 h-8 rounded-full bg-lime-dim border border-lime-border text-lime text-[11px] font-bold flex items-center justify-center hover:bg-[rgba(163,230,53,0.22)] transition-all"
              >
                {initials}
              </button>

              {/* Dropdown menu */}
              {menuOpen && (
                <div className="absolute right-0 top-full mt-2 w-64 z-50 rounded-xl border border-border-light bg-[#1a1f1c] shadow-[0_16px_40px_-8px_rgba(0,0,0,0.5)] overflow-hidden">
                  {/* User header */}
                  <div className="px-4 py-3 border-b border-border-light">
                    <p className="text-sm font-semibold text-text-primary">{user.displayName}</p>
                    <p className="text-[11px] text-text-muted mt-0.5">{user.email}</p>
                    <span className={`inline-block mt-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                      plan === "pro"
                        ? "bg-[rgba(251,191,36,0.1)] text-honey border-[rgba(251,191,36,0.3)]"
                        : "bg-lime-dim text-lime border-lime-border"
                    }`}>
                      {plan === "pro" ? "Pro" : "Free"} plan
                    </span>
                  </div>

                  {/* Usage stats */}
                  <div className="px-4 py-3 border-b border-border-light space-y-2.5">
                    <p className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">Today&apos;s usage</p>

                    <UsageRow
                      label="AI checks"
                      used={checksUsed}
                      limit={limits.checksPerDay}
                    />
                    <UsageRow
                      label="Rewrites"
                      used={0}
                      limit={limits.rewritesPerDay}
                    />
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-text-muted">Word limit</span>
                      <span className="text-text-secondary font-mono">{limits.maxWords.toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="py-1">
                    {plan !== "pro" && (
                      <a
                        href="/pricing"
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-honey hover:bg-bg-glass-hover transition-colors"
                      >
                        <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                          <path d="M8 2L10 6L14 6.5L11 9.5L12 14L8 12L4 14L5 9.5L2 6.5L6 6L8 2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                        </svg>
                        Upgrade to Pro
                      </a>
                    )}
                    <a
                      href="/session"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-text-secondary hover:bg-bg-glass-hover transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                        <path d="M2 4H14M2 8H14M2 12H10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                      </svg>
                      Session history
                    </a>
                    <button
                      onClick={() => { signOut(); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs text-text-muted hover:bg-bg-glass-hover hover:text-error transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                        <path d="M6 2H3V14H6M11 5L14 8L11 11M6 8H14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={startLogin}
              className="btn-primary px-3 py-1 rounded-lg text-xs"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}

function UsageRow({ label, used, limit }: { label: string; used: number; limit: number }) {
  const isUnlimited = limit === -1;
  const pct = isUnlimited ? 0 : limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const atLimit = !isUnlimited && used >= limit;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-text-muted">{label}</span>
        <span className={`font-mono ${atLimit ? "text-error" : "text-text-secondary"}`}>
          {isUnlimited ? `${used} / ∞` : `${used} / ${limit}`}
        </span>
      </div>
      {!isUnlimited && (
        <div className="h-1 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              atLimit ? "bg-error" : pct > 70 ? "bg-warning" : "bg-lime"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
