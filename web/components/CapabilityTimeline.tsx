"use client";

import { useState } from "react";
import type {
  CapabilityData,
  CapabilityLandmark,
  CapabilityMarker,
  SubstanceDetail,
  SubstanceDetailMap,
} from "@/lib/types";

const AXIS_START = 2008;
const AXIS_END = 2021;
const AXIS_TICKS = [2008, 2011, 2014, 2017, 2020];

function yearFrac(date: string): number {
  const [y, m, d] = date.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

function pos(date: string): number {
  const raw = ((yearFrac(date) - AXIS_START) / (AXIS_END - AXIS_START)) * 100;
  return Math.min(100, Math.max(0, raw));
}

function monthsBetween(a: string, b: string): number {
  return Math.round((yearFrac(b) - yearFrac(a)) * 12);
}

function markerColor(type: "media" | "regulator" | "ban"): string {
  if (type === "media") return "var(--status-warning)";
  if (type === "regulator") return "var(--seq-400)";
  return "var(--status-critical)";
}

/** The first independent regulatory concern, else the ban, as the comparison point. */
function comparisonMarker(lm: CapabilityLandmark): CapabilityMarker | null {
  return (
    lm.markers.find((mk) => mk.type === "regulator") ??
    lm.markers.find((mk) => mk.type === "ban") ??
    null
  );
}

function leadLabel(lm: CapabilityLandmark): string | null {
  if (!lm.hazium_flag) return null;
  const cmp = comparisonMarker(lm);
  if (!cmp) return null;
  const months = monthsBetween(lm.hazium_flag.date, cmp.date);
  if (months <= 0) return `${Math.abs(months)} mo behind`;
  const years = Math.round(months / 12);
  const prefix = lm.hazium_flag.lower_bound ? "≥" : "";
  return years >= 2 ? `${prefix}${years} yr ahead` : `${prefix}${months} mo ahead`;
}

export default function CapabilityTimeline({
  data,
  detail,
}: {
  data: CapabilityData;
  detail: SubstanceDetailMap;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const flagged = data.landmarks
    .filter((lm) => lm.hazium_flag !== null)
    .sort((a, b) => {
      const ca = comparisonMarker(a);
      const cb = comparisonMarker(b);
      const la = ca ? monthsBetween(a.hazium_flag!.date, ca.date) : -Infinity;
      const lb = cb ? monthsBetween(b.hazium_flag!.date, cb.date) : -Infinity;
      return lb - la;
    });

  const misses = data.landmarks.filter((lm) => lm.outcome === "miss");
  const dataIssue = data.landmarks.filter((lm) => lm.outcome === "data_issue");

  return (
    <div>
      <Legend />

      <p className="mt-4 text-xs text-text-muted">Click a substance for its use and full rank history.</p>

      <div className="mt-2 space-y-1.5">
        {flagged.map((lm) => (
          <TimelineRow
            key={lm.name}
            lm={lm}
            detail={detail[lm.cas]}
            active={active === lm.name}
            selected={selected === lm.name}
            onEnter={() => setActive(lm.name)}
            onLeave={() => setActive(null)}
            onToggle={() => setSelected(selected === lm.name ? null : lm.name)}
          />
        ))}
      </div>

      {/* Axis */}
      <div className="relative mt-2 h-5 pl-[38%]">
        <div className="relative h-full">
          {AXIS_TICKS.map((yr) => (
            <span
              key={yr}
              className="absolute top-0 -translate-x-1/2 text-[11px] tabular-nums text-text-muted"
              style={{ left: `${pos(`${yr}-01-01`)}%` }}
            >
              {yr}
            </span>
          ))}
        </div>
      </div>

      {(misses.length > 0 || dataIssue.length > 0) && (
        <div className="mt-8 border-t border-hairline pt-6">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            The landmarks it misses{dataIssue.length > 0 ? ", and the open data issue" : ""}
          </h4>
          <div className="mt-3 space-y-2">
            {[...misses, ...dataIssue].map((lm) => (
              <MissRow
                key={lm.name}
                lm={lm}
                detail={detail[lm.cas]}
                tag={lm.outcome === "miss" ? "never flagged" : "excluded, data fix pending"}
                tone={lm.outcome === "miss" ? "critical" : "muted"}
                selected={selected === lm.name}
                onToggle={() => setSelected(selected === lm.name ? null : lm.name)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineRow({
  lm,
  detail,
  active,
  selected,
  onEnter,
  onLeave,
  onToggle,
}: {
  lm: CapabilityLandmark;
  detail: SubstanceDetail | undefined;
  active: boolean;
  selected: boolean;
  onEnter: () => void;
  onLeave: () => void;
  onToggle: () => void;
}) {
  const flag = lm.hazium_flag!;
  const cmp = comparisonMarker(lm);
  const lead = leadLabel(lm);
  const behind = cmp ? monthsBetween(flag.date, cmp.date) <= 0 : false;
  const flagX = pos(flag.date);
  const ban = lm.markers.find((mk) => mk.type === "ban");
  const spanEnd = ban ? pos(ban.date) : flagX;
  const spanStart = Math.min(flagX, spanEnd);
  const spanWidth = Math.abs(spanEnd - flagX);

  return (
    <div className={`rounded-md ${selected ? "bg-surface-raised/50" : ""}`}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={selected}
        className="relative flex cursor-pointer items-center rounded-md py-2 pr-2 transition-colors hover:bg-surface-raised/60"
        onMouseEnter={onEnter}
        onMouseLeave={onLeave}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div className="w-[38%] shrink-0 pr-3">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium text-text-primary">{lm.name}</span>
            {lead && (
              <span
                className="tabular-nums text-xs font-semibold"
                style={{ color: behind ? "var(--status-critical)" : "var(--accent)" }}
              >
                {lead}
              </span>
            )}
            <span className="text-text-muted" aria-hidden>
              {selected ? "▾" : "▸"}
            </span>
          </div>
          <div className="text-[11px] leading-snug text-text-muted">
            {detail?.use ?? lm.hazard}
          </div>
        </div>

        {/* Track */}
        <div className="relative h-8 flex-1">
          <div
            className="absolute top-1/2 h-px -translate-y-1/2"
            style={{
              left: `${spanStart}%`,
              width: `${spanWidth}%`,
              background: "var(--hairline)",
            }}
          />
          {lm.markers.map((mk) => (
            <Marker key={mk.type} marker={mk} />
          ))}
          <HaziumMarker x={flagX} rank={flag.rank} k={flag.k} lowerBound={flag.lower_bound} />
          {active && !selected && <Tooltip lm={lm} />}
        </div>
      </div>

      {selected && <DetailPanel lm={lm} detail={detail} />}
    </div>
  );
}

function DetailPanel({
  lm,
  detail,
}: {
  lm: CapabilityLandmark;
  detail: SubstanceDetail | undefined;
}) {
  const flag = lm.hazium_flag;
  return (
    <div className="mx-1 mb-2 rounded-md border border-hairline bg-page/60 px-4 py-4 text-xs">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm font-medium text-text-primary">{lm.name}</span>
        <span className="text-text-muted">CAS {lm.cas}</span>
      </div>
      {detail?.use && (
        <p className="mt-2 text-text-secondary">
          <span className="text-text-muted">Used as: </span>
          {detail.use}
        </p>
      )}
      <p className="mt-1 text-text-secondary">
        <span className="text-text-muted">Hazard behind the ban: </span>
        {lm.hazard}
      </p>

      {detail?.trajectory && detail.trajectory.length > 1 && (
        <div className="mt-4">
          <div className="mb-1 text-text-muted">
            Rank among all approved substances, by year (lower is more concerning):
          </div>
          <RankTrajectory trajectory={detail.trajectory} />
        </div>
      )}

      <div className="mt-4 space-y-1.5 border-t border-hairline pt-3">
        {flag && (
          <div className="flex items-start gap-2">
            <span
              className="mt-0.5 inline-block h-2 w-2 shrink-0 rotate-45 rounded-[1px]"
              style={{ background: "var(--accent)" }}
              aria-hidden
            />
            <span className="text-text-secondary">
              Hazium first flagged it {flag.date.slice(0, 4)}
              {flag.lower_bound ? " or earlier" : ""}: rank {flag.rank}, top {flag.k}.
            </span>
          </div>
        )}
        {lm.markers.map((mk) => (
          <div key={mk.type} className="flex items-start gap-2">
            <span
              className={`mt-0.5 inline-block h-2 w-2 shrink-0 ${mk.type === "ban" ? "rounded-[1px]" : "rounded-full"}`}
              style={{ background: markerColor(mk.type) }}
              aria-hidden
            />
            <span className="text-text-secondary">
              {mk.date.slice(0, mk.precision === "day" ? 10 : 7)}: {mk.label}.{" "}
              <a
                href={mk.url}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                {mk.source}
              </a>
            </span>
          </div>
        ))}
      </div>

      <p className="mt-3 leading-relaxed text-text-secondary">{lm.note}</p>
    </div>
  );
}

function RankTrajectory({ trajectory }: { trajectory: { year: number; rank: number }[] }) {
  const W = 480;
  const H = 130;
  const padL = 30;
  const padR = 10;
  const padT = 10;
  const padB = 20;
  const years = trajectory.map((p) => p.year);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const maxRank = Math.max(...trajectory.map((p) => p.rank));
  const cap = Math.max(50, Math.min(150, maxRank));
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const x = (yr: number) =>
    padL + (maxYear === minYear ? 0 : ((yr - minYear) / (maxYear - minYear)) * plotW);
  // rank 1 at top (most concerning), cap at bottom
  const y = (rank: number) => padT + ((Math.min(rank, cap) - 1) / (cap - 1)) * plotH;
  const line = trajectory.map((p) => `${x(p.year)},${y(p.rank)}`).join(" ");
  const top20Y = y(20);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Rank trajectory over time">
      {/* top-20 danger band */}
      <rect x={padL} y={padT} width={plotW} height={top20Y - padT} fill="var(--status-critical)" opacity="0.08" />
      <line x1={padL} y1={top20Y} x2={W - padR} y2={top20Y} stroke="var(--status-critical)" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.5" />
      <text x={W - padR} y={top20Y - 2} textAnchor="end" fontSize="9" fill="var(--status-critical)" opacity="0.8">
        top 20
      </text>
      {/* y-axis labels */}
      <text x={padL - 4} y={padT + 4} textAnchor="end" fontSize="9" fill="var(--text-muted)">1</text>
      <text x={padL - 4} y={padT + plotH} textAnchor="end" fontSize="9" fill="var(--text-muted)">{cap}</text>
      {/* rank line */}
      <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="1.6" strokeLinejoin="round" />
      {trajectory.map((p) => (
        <circle key={p.year} cx={x(p.year)} cy={y(p.rank)} r="2.4" fill="var(--accent)" />
      ))}
      {/* x-axis year labels (first, middle, last) */}
      {[minYear, Math.round((minYear + maxYear) / 2), maxYear].map((yr) => (
        <text key={yr} x={x(yr)} y={H - 6} textAnchor="middle" fontSize="9" fill="var(--text-muted)">
          {yr}
        </text>
      ))}
    </svg>
  );
}

function HaziumMarker({
  x,
  rank,
  k,
  lowerBound,
}: {
  x: number;
  rank: number;
  k: number;
  lowerBound: boolean;
}) {
  return (
    <span
      className="absolute top-1/2 z-10 -translate-x-1/2 -translate-y-1/2"
      style={{ left: `${x}%` }}
      aria-label={`Hazium flagged: rank ${rank}, top ${k}`}
    >
      <span
        className="block h-3 w-3 rotate-45 rounded-[2px] ring-2 ring-page"
        style={{ background: "var(--accent)" }}
      />
      {lowerBound && (
        <span
          className="absolute right-full top-1/2 mr-0.5 -translate-y-1/2 text-[10px] leading-none text-text-muted"
          aria-hidden
        >
          &lt;
        </span>
      )}
    </span>
  );
}

function Marker({ marker }: { marker: CapabilityMarker }) {
  const x = pos(marker.date);
  if (marker.type === "media") {
    return (
      <span
        className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ left: `${x}%` }}
        aria-label={`Public: ${marker.label}`}
      >
        <span
          className="block"
          style={{
            width: 0,
            height: 0,
            borderLeft: "5px solid transparent",
            borderRight: "5px solid transparent",
            borderBottom: "9px solid var(--status-warning)",
            filter: "drop-shadow(0 0 1px var(--page))",
          }}
        />
      </span>
    );
  }
  if (marker.type === "regulator") {
    return (
      <span
        className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ left: `${x}%` }}
        aria-label={`Regulator: ${marker.label}`}
      >
        <span
          className="block h-2.5 w-2.5 rounded-full ring-2 ring-page"
          style={{ background: "var(--seq-400)" }}
        />
      </span>
    );
  }
  return (
    <span
      className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
      style={{ left: `${x}%` }}
      aria-label={`EU action: ${marker.label}`}
    >
      <span
        className="block h-2.5 w-2.5 rounded-[1px] ring-2 ring-page"
        style={{ background: "var(--status-critical)" }}
      />
    </span>
  );
}

function Tooltip({ lm }: { lm: CapabilityLandmark }) {
  const flag = lm.hazium_flag;
  return (
    <div className="absolute bottom-full left-0 z-20 mb-2 w-max max-w-sm rounded-md border border-hairline bg-surface-raised px-3 py-2 text-xs shadow-lg">
      <div className="font-medium text-text-primary">
        {lm.name} <span className="text-text-muted">· {lm.cas}</span>
      </div>
      {flag && (
        <div className="mt-1 flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rotate-45 rounded-[1px]" style={{ background: "var(--accent)" }} aria-hidden />
          <span className="text-text-secondary">
            Hazium: rank {flag.rank} (top {flag.k}), {flag.date.slice(0, 4)}
            {flag.lower_bound ? " or earlier" : ""}
          </span>
        </div>
      )}
      {lm.markers.map((mk) => (
        <div key={mk.type} className="mt-1 flex items-start gap-1.5">
          <span
            className={`mt-0.5 inline-block h-2 w-2 shrink-0 ${mk.type === "ban" ? "rounded-[1px]" : "rounded-full"}`}
            style={{ background: markerColor(mk.type) }}
            aria-hidden
          />
          <span className="text-text-secondary">
            {mk.date.slice(0, mk.precision === "day" ? 10 : 7)}: {mk.label}
          </span>
        </div>
      ))}
      <p className="mt-2 border-t border-hairline pt-2 leading-relaxed text-text-secondary">
        {lm.note}
      </p>
    </div>
  );
}

function MissRow({
  lm,
  detail,
  tag,
  tone,
  selected,
  onToggle,
}: {
  lm: CapabilityLandmark;
  detail: SubstanceDetail | undefined;
  tag: string;
  tone: "critical" | "muted";
  selected: boolean;
  onToggle: () => void;
}) {
  const color = tone === "critical" ? "var(--status-critical)" : "var(--text-muted)";
  return (
    <div className={`rounded-md ${selected ? "bg-surface-raised/50" : ""}`}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={selected}
        className="cursor-pointer rounded-md px-1 py-1.5 transition-colors hover:bg-surface-raised/60"
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-text-primary">{lm.name}</span>
          <span className="text-xs font-semibold" style={{ color }}>
            {tag}
          </span>
          <span className="text-xs text-text-muted" aria-hidden>
            {selected ? "▾" : "▸"}
          </span>
        </div>
        <div className="text-[11px] leading-snug text-text-muted">{detail?.use ?? lm.hazard}</div>
      </div>
      {selected && <DetailPanel lm={lm} detail={detail} />}
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rotate-45 rounded-[2px]" style={{ background: "var(--accent)" }} aria-hidden />
        Hazium first flags it (enters the top riskiest)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block"
          style={{
            width: 0,
            height: 0,
            borderLeft: "5px solid transparent",
            borderRight: "5px solid transparent",
            borderBottom: "9px solid var(--status-warning)",
          }}
          aria-hidden
        />
        Public controversy (where one existed)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "var(--seq-400)" }} aria-hidden />
        Regulator&apos;s first public concern
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-[1px]" style={{ background: "var(--status-critical)" }} aria-hidden />
        Final EU ban
      </span>
    </div>
  );
}
