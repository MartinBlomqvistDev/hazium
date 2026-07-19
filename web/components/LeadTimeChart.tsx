"use client";

import { useState } from "react";
import type { Landmark } from "@/lib/types";

function bestLead(lm: Landmark): number | null {
  return lm.lead_time_months["10"] ?? lm.lead_time_months["20"] ?? lm.lead_time_months["50"];
}

export default function LeadTimeChart({ landmarks }: { landmarks: Landmark[] }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const sorted = [...landmarks].sort((a, b) => {
    const la = bestLead(a);
    const lb = bestLead(b);
    if (la === null && lb === null) return 0;
    if (la === null) return 1;
    if (lb === null) return -1;
    return lb - la;
  });
  const max = Math.max(...sorted.map((lm) => bestLead(lm) ?? 0), 1);

  return (
    <div>
      <div className="mb-4 flex items-center gap-5 text-xs text-text-secondary">
        <LegendDot color="var(--status-good)" label="flagged before the real EU action" />
        <LegendDot color="var(--status-critical)" label="never flagged (a real miss, reported)" />
      </div>
      <div className="space-y-2.5">
        {sorted.map((lm) => {
          const lead = bestLead(lm);
          const isHovered = hovered === lm.name;
          return (
            <div
              key={lm.name}
              className="relative"
              onMouseEnter={() => setHovered(lm.name)}
              onMouseLeave={() => setHovered(null)}
            >
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium text-text-primary">{lm.name}</span>
                <span className="tabular-nums text-text-secondary">
                  {lead !== null ? `${lead} mo lead` : "not flagged"}
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface">
                {lead !== null ? (
                  <div
                    className="h-full rounded-full transition-[filter]"
                    style={{
                      width: `${Math.max((lead / max) * 100, 3)}%`,
                      background: "var(--status-good)",
                      filter: isHovered ? "brightness(1.25)" : undefined,
                    }}
                  />
                ) : (
                  <div
                    className="h-full rounded-full"
                    style={{ width: "3%", background: "var(--status-critical)" }}
                  />
                )}
              </div>
              {isHovered && (
                <div className="absolute left-0 top-full z-10 mt-1 w-max max-w-xs rounded-md border border-hairline bg-surface-raised px-3 py-2 text-xs text-text-secondary shadow-lg">
                  <div className="font-medium text-text-primary">
                    {lm.name} · {lm.cas}
                  </div>
                  <div className="mt-0.5">{lm.note}</div>
                  <div className="mt-0.5">Real EU action: {lm.action_date}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: color }}
        aria-hidden
      />
      {label}
    </span>
  );
}
