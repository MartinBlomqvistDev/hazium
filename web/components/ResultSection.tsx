import type { CapabilityData, HewbData, SubstanceDetailMap } from "@/lib/types";
import CapabilityTimeline from "./CapabilityTimeline";

export default function ResultSection({
  data,
  capability,
  detail,
}: {
  data: HewbData;
  capability: CapabilityData;
  detail: SubstanceDetailMap;
}) {
  return (
    <section id="result" className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          The result: HEWB
        </h2>
        <p className="mt-4 text-text-secondary">
          The <strong className="text-text-primary">Hazium Early Warning Benchmark</strong>{" "}
          fixes ten historical EU pesticide bans, real regulatory actions, not
          hypothetical cases. At each annual cutoff from 2009, using only evidence
          dated before that cutoff, it asks where Hazium would have ranked the
          substance among the thousands of approved actives of that year.
        </p>
        <p className="mt-4 text-text-secondary">
          Months before the ban is the easy number. The harder question, and the
          one that shows capability, is whether Hazium was ahead of the
          independent world: the regulator&apos;s first public concern, which
          arrives long before the final paperwork. The literature signal became a
          model input, so it is left out of this comparison; what remains are
          dated regulatory milestones the model never sees.
        </p>

        <div className="mt-10 rounded-xl border border-hairline bg-surface p-5 sm:p-7">
          <CapabilityTimeline data={capability} detail={detail} />
        </div>

        <p className="mt-6 text-sm leading-relaxed text-text-secondary">
          On the developmental-neurotoxicity and reprotoxic cases, chlorpyrifos,
          its methyl sister, thiacloprid, and mancozeb, Hazium ranked the
          substance among the riskiest roughly a decade before EFSA&apos;s first
          public concern. On the neonicotinoids it was early relative to the
          2013 EU restriction, though national bans were already emerging. On
          dimethoate it moved level with the regulator, and on imidacloprid it
          flagged late; both are on the chart. Epoxiconazole it never flagged at
          all. Where a substance had a real public controversy, the chart marks
          that too: Hazium flagged chlorpyrifos years before its 2015 US ban
          fight, and the neonicotinoids before the 2012 bee campaign. Most
          landmarks had no public profile at all when Hazium flagged them.
        </p>

        <p className="mt-6 text-xs text-text-muted">
          HEWB v{data.hewb_version}. Flag dates come from the frozen benchmark
          run under strict pre-cutoff evidence discipline; out-of-fold scores are
          averaged over repeated cross-validation, so the ranks hold steady
          across resampling. Regulatory milestone dates are
          hand-verified against the enacting act or EFSA output.
        </p>
      </div>
    </section>
  );
}
