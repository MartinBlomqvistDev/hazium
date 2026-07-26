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
          hypothetical cases. It then works through every annual cutoff from 2009,
          using only evidence dated before each one. The question at each cutoff is
          where Hazium would have ranked the substance among everything the graph
          knew about that year, roughly 5,900 substances.
        </p>
        <p className="mt-4 text-text-secondary">
          Months before the ban is the easy number. The stricter comparison is
          against the regulator&apos;s first public concern, which arrives long
          before the final paperwork. The literature signal became a model input,
          so it is left out of this comparison; what remains are dated regulatory
          milestones the model never sees.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Before reading the chart, read what it is not. These lead times are
          real, and they are also{" "}
          <strong className="text-text-primary">reproducible without a model</strong>. Ranking on
          approval age alone puts chlorpyrifos in the danger band at the same 132 months. The
          timeline records <em>when</em> a substance entered the riskiest band. It is not evidence
          that the evidence put it there, and that distinction is{" "}
          <a href="#how" className="text-accent underline underline-offset-2">
            what the previous section is about
          </a>
          .
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

        <div className="mt-8 rounded-lg border border-hairline bg-page p-5">
          <h3 className="font-medium text-text-primary">
            The test that passed, and the thing it could not see
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            A ranking model with 25 positives in 5,933 substances can look good by accident. So
            the labels were permuted and the whole thing refitted, fifty times. Real average
            precision is 0.230 against a shuffled maximum of 0.013, p&nbsp;=&nbsp;0.020. The
            result is not noise.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            That test asks one question: can the model beat chance. It cannot ask whether
            something simpler beats the model. Nothing in a permutation test would ever have
            surfaced approval age, and nothing did. Only running the baseline did.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            This version stays published and is not retracted, because its numbers are correct
            for the question it asked. Both are citable datasets:{" "}
            <a
              href="https://huggingface.co/datasets/MartinBlomqvist/hewb"
              className="text-accent underline underline-offset-2"
            >
              HEWB v1.4 and v2 on HuggingFace
            </a>
            , CC-BY-4.0.
          </p>
        </div>

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
