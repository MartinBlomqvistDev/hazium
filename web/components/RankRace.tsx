"use client";

import { useEffect, useMemo, useState } from "react";
import type { RankRaceData } from "@/lib/types";

const DISPLAY_N = 14;
const ROW_H = 26;
const STEP_MS = 1300;

function shortName(name: string): string {
  return name.length > 26 ? name.slice(0, 25) + "…" : name;
}

export default function RankRace({ data }: { data: RankRaceData }) {
  const { years, per_year } = data;
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const year = years[idx];
  const isLast = idx >= years.length - 1;

  const { union, maxScore } = useMemo(() => {
    const u = new Map<string, { cas: string; name: string; banned: number | null }>();
    let mx = 0;
    for (const y of years) {
      for (const r of per_year[String(y)]) {
        if (!u.has(r.cas)) u.set(r.cas, { cas: r.cas, name: r.name, banned: r.banned_year });
        if (r.score > mx) mx = r.score;
      }
    }
    return { union: [...u.values()], maxScore: mx || 1 };
  }, [years, per_year]);

  const cur = useMemo(() => {
    const m = new Map<string, { rank: number; score: number }>();
    for (const r of per_year[String(year)]) m.set(r.cas, { rank: r.rank, score: r.score });
    return m;
  }, [per_year, year]);

  useEffect(() => {
    if (!playing || isLast) return;
    const t = setTimeout(() => setIdx((i) => i + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, idx, isLast]);

  const bannedInTop = per_year[String(year)]
    .filter((r) => r.rank <= DISPLAY_N && r.banned_year != null)
    .length;

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (isLast) {
              setIdx(0);
              setPlaying(true);
            } else {
              setPlaying((p) => !p);
            }
          }}
          className="rounded-md border border-hairline bg-surface px-3 py-1 text-sm text-text-primary transition-colors hover:bg-surface-raised"
        >
          {isLast ? "Replay" : playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          min={0}
          max={years.length - 1}
          value={idx}
          aria-label="Year"
          onChange={(e) => {
            setPlaying(false);
            setIdx(Number(e.target.value));
          }}
          className="h-1 flex-1 cursor-pointer accent-[var(--accent)]"
        />
        <span className="w-12 text-right text-2xl font-semibold tabular-nums" style={{ color: "var(--accent)" }}>
          {year}
        </span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-text-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--status-critical)", opacity: 0.85 }} aria-hidden />
          later EU-banned
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--seq-400)", opacity: 0.6 }} aria-hidden />
          still approved
        </span>
        <span className="text-text-muted">
          {bannedInTop} of the top {DISPLAY_N} this year were later banned
        </span>
      </div>

      <div className="relative" style={{ height: DISPLAY_N * ROW_H }}>
        {union.map((s) => {
          const c = cur.get(s.cas);
          const visible = !!c && c.rank <= DISPLAY_N;
          const top = visible ? (c!.rank - 1) * ROW_H : DISPLAY_N * ROW_H;
          const w = c ? (c.score / maxScore) * 100 : 0;
          const banned = s.banned != null;
          return (
            <div
              key={s.cas}
              className="absolute inset-x-0 flex items-center gap-2 transition-all duration-700 ease-out"
              style={{ transform: `translateY(${top}px)`, opacity: visible ? 1 : 0, height: ROW_H }}
            >
              <span className="w-5 shrink-0 text-right text-[11px] tabular-nums text-text-muted">
                {c?.rank ?? ""}
              </span>
              <div
                className="h-4 shrink-0 rounded-sm transition-all duration-700 ease-out"
                style={{
                  width: `${Math.max(w, 1)}%`,
                  background: banned ? "var(--status-critical)" : "var(--seq-400)",
                  opacity: banned ? 0.85 : 0.55,
                }}
              />
              <span className="whitespace-nowrap text-xs text-text-secondary">
                {shortName(s.name)}
                {banned && (
                  <span className="ml-1.5 text-[10px] text-status-critical/80">
                    banned {s.banned}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
