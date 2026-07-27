import Link from "next/link";
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
          The first benchmark, and what its lead times measure
        </h2>
        <p className="mt-4 text-text-secondary">
          The <strong className="text-text-primary">Hazium Early Warning Benchmark</strong>{" "}
          fixes ten historical EU pesticide bans, real regulatory actions, not
          hypothetical cases. It then works through every annual cutoff from 2009,
          using only evidence dated before each one, and records the earliest year
          each substance entered the riskiest twenty of roughly 5,900.
        </p>
        <div className="mt-6 rounded-lg border border-status-critical/40 bg-page p-5">
          <h3 className="font-medium text-text-primary">Read the lead times as a window, not a warning</h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Chlorpyrifos is marked 132 months ahead of its 2020 ban. That is January 2009, the
            first cutoff tested, so the number says it was already ranked high when the window
            opened rather than that the model saw it coming.{" "}
            <strong className="text-text-primary">
              Seven of the ten were in the top twenty at or within two years of that first cutoff
            </strong>
            , and ranking on approval age alone reproduces the same dates.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The pattern across the whole chart is one thing: early on substances that were
            already old and heavily assessed in 2009, four years <em>behind</em> the regulator on
            imidacloprid, level on dimethoate, and absent on epoxiconazole. A benchmark whose
            headline metric is bounded by its own start date cannot separate foresight from
            seniority, which is why{" "}
            <Link href="/" className="text-accent underline underline-offset-2">
              the question was reformulated
            </Link>{" "}
            and the survival result is what this project now reports.
          </p>
        </div>
        <p className="mt-6 text-sm leading-relaxed text-text-secondary">
          What the chart still shows honestly is the comparison against the regulator&apos;s own
          first public concern, a dated milestone the model never reads. The literature signal is
          a model input, so it is excluded from that comparison.
        </p>

        <div className="mt-10 rounded-xl border border-hairline bg-surface p-5 sm:p-7">
          <CapabilityTimeline data={capability} detail={detail} />
        </div>

        <p className="mt-6 text-sm leading-relaxed text-text-secondary">
          Case by case: on chlorpyrifos, its methyl sister, thiacloprid and mancozeb the
          substance sat among the riskiest roughly a decade before EFSA&apos;s first public
          concern, though all four were long-standing approvals by 2009. On the neonicotinoids it
          was early relative to the 2013 EU restriction, with national bans already emerging. On
          dimethoate it moved level with the regulator, on imidacloprid it flagged four years
          late, and epoxiconazole it never flagged. Where a substance had a real public
          controversy the chart marks that too, and most landmarks had no public profile at all
          at the point they entered the band.
        </p>

        <div className="mt-8 rounded-lg border border-hairline bg-page p-5">
          <h3 className="font-medium text-text-primary">
            What a permutation test can and cannot rule out
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            A ranking model with 25 positives in 5,933 substances can look good by accident. So
            the labels were permuted and the whole thing refitted, fifty times. Real average
            precision is 0.230 against a shuffled maximum of 0.013, p&nbsp;=&nbsp;0.020. The
            result is not noise.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            That answers one question: can the model beat chance. It cannot answer whether
            something simpler beats the model. No permutation test would surface approval age,
            because only running the baseline does.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Both versions stay published, each correct for the question it asked, and both are
            citable datasets:{" "}
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
