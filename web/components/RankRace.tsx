"use client";

import { useEffect, useMemo, useState } from "react";
import type { RankRaceData, SubstanceDetailMap } from "@/lib/types";

const DISPLAY_N = 10;
const ROW_H = 30;
const STEP_MS = 1600;

function shortName(name: string): string {
  return name.length > 26 ? name.slice(0, 25) + "…" : name;
}

export default function RankRace({
  data,
  detail,
}: {
  data: RankRaceData;
  detail: SubstanceDetailMap;
}) {
  const { years, per_year, top_n } = data;
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
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

  // Full arc of the selected substance across every year, for the detail panel.
  const selectedArc = useMemo(() => {
    if (!selected) return null;
    const meta = union.find((s) => s.cas === selected);
    if (!meta) return null;
    const points = years.map((y) => {
      const row = per_year[String(y)].find((r) => r.cas === selected);
      return { year: y, rank: row ? row.rank : null };
    });
    const present = points.filter((p) => p.rank !== null) as { year: number; rank: number }[];
    const best = present.reduce(
      (acc, p) => (p.rank < acc.rank ? p : acc),
      present[0] ?? { year: years[0], rank: top_n },
    );
    return { meta, points, best, seasons: present.length, use: detail[selected]?.use };
  }, [selected, union, years, per_year, detail, top_n]);

  useEffect(() => {
    if (!playing || isLast) return;
    const t = setTimeout(() => setIdx((i) => i + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, idx, isLast]);

  const bannedInTop = per_year[String(year)].filter(
    (r) => r.rank <= DISPLAY_N && r.banned_year != null,
  ).length;

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
        <span
          className="w-12 text-right text-2xl font-semibold tabular-nums"
          style={{ color: "var(--accent)" }}
        >
          {year}
        </span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-text-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-4 rounded-sm"
            style={{ background: "var(--status-critical)", opacity: 0.85 }}
            aria-hidden
          />
          later EU-banned
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-4 rounded-sm"
            style={{ background: "var(--seq-400)", opacity: 0.6 }}
            aria-hidden
          />
          still approved
        </span>
        <span className="text-text-muted">
          {bannedInTop} of the top {DISPLAY_N} this year were later banned
        </span>
        <span className="text-text-muted">· click a substance to follow it</span>
      </div>

      <div className="relative" style={{ height: DISPLAY_N * ROW_H }}>
        {union.map((s) => {
          const c = cur.get(s.cas);
          const visible = !!c && c.rank <= DISPLAY_N;
          const top = visible ? (c!.rank - 1) * ROW_H : DISPLAY_N * ROW_H;
          const w = c ? (c.score / maxScore) * 100 : 0;
          const banned = s.banned != null;
          const isSel = selected === s.cas;
          const dim = selected != null && !isSel;
          return (
            <button
              type="button"
              key={s.cas}
              onClick={() => setSelected((prev) => (prev === s.cas ? null : s.cas))}
              className="absolute inset-x-0 flex cursor-pointer items-center gap-2 rounded-sm text-left transition-all duration-700 ease-out"
              style={{
                transform: `translateY(${top}px)`,
                opacity: visible ? (dim ? 0.28 : 1) : 0,
                height: ROW_H,
                pointerEvents: visible ? "auto" : "none",
                boxShadow: isSel ? "inset 0 0 0 1px var(--accent)" : undefined,
                background: isSel ? "var(--surface-raised)" : undefined,
              }}
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
              <span
                className={`whitespace-nowrap text-xs ${isSel ? "font-semibold text-text-primary" : "text-text-secondary"}`}
              >
                {shortName(s.name)}
                {banned && (
                  <span className="ml-1.5 text-[10px] text-status-critical/80">
                    banned {s.banned}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {selectedArc && (
        <div className="mt-4 rounded-lg border border-hairline bg-surface-raised/60 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-text-primary">
                {selectedArc.meta.name}
                {selectedArc.meta.banned != null && (
                  <span className="ml-2 text-xs font-normal text-status-critical/90">
                    EU-banned {selectedArc.meta.banned}
                  </span>
                )}
              </div>
              <div className="text-xs text-text-muted">
                CAS {selectedArc.meta.cas} · peak rank #{selectedArc.best.rank} in{" "}
                {selectedArc.best.year} · in the top {top_n} for {selectedArc.seasons} of{" "}
                {years.length} cutoffs
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="shrink-0 rounded-md border border-hairline px-2 py-0.5 text-xs text-text-secondary transition-colors hover:bg-surface"
            >
              Close
            </button>
          </div>

          {selectedArc.use && (
            <p className="mt-2 text-xs leading-relaxed text-text-secondary">
              <span className="text-text-muted">Used for: </span>
              {selectedArc.use}
            </p>
          )}

          <RankArc points={selectedArc.points} topN={top_n} currentYear={year} />
        </div>
      )}
    </div>
  );
}

function RankArc({
  points,
  topN,
  currentYear,
}: {
  points: { year: number; rank: number | null }[];
  topN: number;
  currentYear: number;
}) {
  const W = 320;
  const H = 84;
  const padX = 8;
  const padY = 10;
  const n = points.length;
  const x = (i: number) => padX + (i / Math.max(n - 1, 1)) * (W - 2 * padX);
  // rank 1 at the top, topN at the bottom
  const y = (rank: number) => padY + ((rank - 1) / Math.max(topN - 1, 1)) * (H - 2 * padY);

  // Break the polyline on gaps (years the substance left the top-N).
  const segments: string[] = [];
  let run: string[] = [];
  points.forEach((p, i) => {
    if (p.rank == null) {
      if (run.length) segments.push(run.join(" "));
      run = [];
    } else {
      run.push(`${x(i).toFixed(1)},${y(p.rank).toFixed(1)}`);
    }
  });
  if (run.length) segments.push(run.join(" "));

  const curIdx = points.findIndex((p) => p.year === currentYear);
  const curPoint = curIdx >= 0 ? points[curIdx] : null;

  return (
    <div className="mt-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Rank over time">
        {/* current-year guide */}
        {curIdx >= 0 && (
          <line
            x1={x(curIdx)}
            y1={padY}
            x2={x(curIdx)}
            y2={H - padY}
            stroke="var(--accent)"
            strokeWidth={1}
            strokeDasharray="2 2"
            opacity={0.5}
          />
        )}
        {segments.map((pts, i) => (
          <polyline
            key={i}
            points={pts}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {points.map(
          (p, i) =>
            p.rank != null && (
              <circle
                key={i}
                cx={x(i)}
                cy={y(p.rank)}
                r={p.year === currentYear ? 3.2 : 1.8}
                fill={p.year === currentYear ? "var(--accent)" : "var(--seq-400)"}
              />
            ),
        )}
      </svg>
      <div className="flex justify-between text-[10px] text-text-muted">
        <span>{points[0]?.year}</span>
        <span>
          {curPoint?.rank != null
            ? `rank #${curPoint.rank} in ${currentYear}`
            : `outside top ${topN} in ${currentYear}`}
        </span>
        <span>{points[points.length - 1]?.year}</span>
      </div>
    </div>
  );
}
