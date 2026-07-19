"use client";

import { useState } from "react";
import type { CapabilityData, CapabilityLandmark, CapabilityMarker } from "@/lib/types";

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

export default function CapabilityTimeline({ data }: { data: CapabilityData }) {
  const [active, setActive] = useState<string | null>(null);

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

      <div className="mt-6 space-y-1.5">
        {flagged.map((lm) => (
          <TimelineRow
            key={lm.name}
            lm={lm}
            active={active === lm.name}
            onEnter={() => setActive(lm.name)}
            onLeave={() => setActive(null)}
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
            Reported alongside: the misses{dataIssue.length > 0 ? " and the open data issue" : ""}
          </h4>
          <div className="mt-3 space-y-3">
            {misses.map((lm) => (
              <HonestRow key={lm.name} lm={lm} tag="never flagged" tone="critical" />
            ))}
            {dataIssue.map((lm) => (
              <HonestRow key={lm.name} lm={lm} tag="excluded, data fix pending" tone="muted" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineRow({
  lm,
  active,
  onEnter,
  onLeave,
}: {
  lm: CapabilityLandmark;
  active: boolean;
  onEnter: () => void;
  onLeave: () => void;
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
    <div
      className="relative flex items-center rounded-md py-2 pr-2 transition-colors hover:bg-surface-raised/60"
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
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
        </div>
        <div className="text-[11px] text-text-muted">{lm.hazard}</div>
      </div>

      {/* Track */}
      <div className="relative h-8 flex-1">
        {/* span line from Hazium flag to ban */}
        <div
          className="absolute top-1/2 h-px -translate-y-1/2"
          style={{
            left: `${spanStart}%`,
            width: `${spanWidth}%`,
            background: "var(--hairline)",
          }}
        />
        {/* regulator + ban markers */}
        {lm.markers.map((mk) => (
          <Marker key={mk.type} marker={mk} />
        ))}
        {/* Hazium flag marker (drawn last, on top) */}
        <HaziumMarker x={flagX} rank={flag.rank} k={flag.k} lowerBound={flag.lower_bound} />

        {active && (
          <Tooltip lm={lm} />
        )}
      </div>
    </div>
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

function HonestRow({
  lm,
  tag,
  tone,
}: {
  lm: CapabilityLandmark;
  tag: string;
  tone: "critical" | "muted";
}) {
  const color = tone === "critical" ? "var(--status-critical)" : "var(--text-muted)";
  return (
    <div className="text-sm">
      <div className="flex items-baseline gap-2">
        <span className="font-medium text-text-primary">{lm.name}</span>
        <span className="text-xs font-semibold" style={{ color }}>
          {tag}
        </span>
      </div>
      <p className="mt-0.5 text-xs leading-relaxed text-text-secondary">{lm.note}</p>
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
