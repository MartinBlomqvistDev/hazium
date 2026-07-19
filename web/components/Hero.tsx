import type { HewbData } from "@/lib/types";

export default function Hero({ data }: { data: HewbData }) {
  const { headline } = data;
  return (
    <section id="top" className="border-b border-hairline">
      <div className="mx-auto max-w-5xl px-6 py-20 sm:py-28">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1 text-xs text-text-secondary">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-status-warning" aria-hidden />
          HEWB v{data.hewb_version} — provisional, being re-run
        </div>
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Would public data have caught it{" "}
          <span className="text-accent">before regulators did?</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-text-secondary">
          Hazium builds a temporally-aware knowledge graph over EU pesticide
          approvals, hazard classifications, and scientific literature — then
          asks a falsifiable question of it: ranking substances for future
          regulatory risk using only evidence that existed at the time,
          measured against real EU bans that happened years later.
        </p>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Stat
            value={`${headline.landmarks_flagged} / ${headline.landmarks_total}`}
            label="landmark EU bans flagged in advance"
          />
          <Stat
            value={
              headline.best_lead_time_months
                ? `${headline.best_lead_time_months} mo`
                : "—"
            }
            label={
              headline.best_lead_time_case
                ? `earliest lead time (${headline.best_lead_time_case})`
                : "earliest lead time"
            }
          />
          <Stat value="2009–2024" label="annual rolling-origin cutoffs tested" />
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="tabular-nums text-3xl font-semibold text-text-primary">{value}</div>
      <div className="mt-1 text-sm text-text-secondary">{label}</div>
    </div>
  );
}
