import type { HewbData } from "@/lib/types";
import LeadTimeChart from "./LeadTimeChart";

export default function ResultSection({ data }: { data: HewbData }) {
  const missed = data.landmarks.filter((lm) => !lm.flagged);
  return (
    <section id="result" className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          The result: HEWB
        </h2>
        <p className="mt-4 text-text-secondary">
          The <strong className="text-text-primary">Hazium Early Warning Benchmark</strong>{" "}
          fixes ten historical EU non-renewals, real bans, not hypothetical
          cases, and asks: at each annual cutoff from 2009 onward, using
          only evidence dated before that cutoff, where would Hazium have
          ranked this substance? Lead time is measured in months between the
          earliest cutoff where a substance entered the top 10 riskiest
          substances and the real EU action.
        </p>

        <div className="mt-10 rounded-xl border border-hairline bg-surface p-6 sm:p-8">
          <LeadTimeChart landmarks={data.landmarks} />
        </div>

        {missed.length > 0 && (
          <div className="mt-6 rounded-lg border border-status-critical/30 bg-status-critical/[0.06] p-4 text-sm">
            <p className="text-text-primary">
              {missed.map((m) => m.name).join(", ")} never entered the top 50
              before its real action. Every HEWB result is published against
              its baseline and its misses.
            </p>
          </div>
        )}

        {data.provisional && (
          <p className="mt-6 text-xs text-text-muted">{data.provisional_note}</p>
        )}
      </div>
    </section>
  );
}
