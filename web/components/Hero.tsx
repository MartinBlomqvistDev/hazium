import type { SurvivalData } from "@/lib/types";

/**
 * The hero used to lead with 7/10 landmark bans and a 132-month lead time.
 * Both are real, and both are reproducible by subtracting two dates, which the
 * page went on to admit five screens later. Opening with the strong version of
 * a claim and retracting it further down is not honesty, it is a page arguing
 * with itself.
 *
 * These three numbers are what survives scrutiny: what the evidence adds over
 * that date subtraction, what that is worth in a forward test, and the case the
 * project was built for and still misses.
 */
export default function Hero({ survival }: { survival: SurvivalData }) {
  const h1 = survival.horizon_1;
  const age = h1.arms["age only"].average_precision;
  const both = h1.arms["age + evidence"].average_precision;
  const split = h1.quoted_split;
  const cohort = survival.anchor_cohort;

  return (
    <section id="top" className="border-b border-hairline">
      <div className="mx-auto max-w-5xl px-6 py-20 sm:py-28">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1 text-xs text-text-secondary">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--status-good)" }}
            aria-hidden
          />
          HEWB v{survival.version}
        </div>
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Can public evidence tell you{" "}
          <span className="text-accent">which pesticide falls next?</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-text-secondary">
          Hazium builds a temporally-aware knowledge graph over EU pesticide
          approvals, hazard classifications, sales and scientific literature,
          then ranks approved substances for withdrawal risk using only evidence
          that existed at the time.
        </p>
        <p className="mt-4 max-w-2xl text-text-secondary">
          The answer is partly, and by less than the first version of this page
          claimed. The honest measure is how far the evidence gets past the one
          thing that predicts a withdrawal with no model at all: how long the
          substance has held approval.
        </p>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Stat
            value={`${age.toFixed(3)} → ${both.toFixed(3)}`}
            label="average precision from approval age alone, then with the evidence added"
          />
          {split && (
            <Stat
              value={`${split.both_hits_at_50} vs ${split.age_hits_at_50}`}
              label={`real withdrawals in the top 50, fit on ${split.train_through} and scored forward, against the same baseline`}
            />
          )}
          <Stat
            value={`${cohort.hits_in_top_k} of ${cohort.size}`}
            label={`substances found from the reevaluation that prompted this project, where chance gives ${cohort.expected_in_top_k}`}
            tone="critical"
          />
        </div>
      </div>
    </section>
  );
}

function Stat({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone?: "critical";
}) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div
        className="tabular-nums text-3xl font-semibold"
        style={{ color: tone === "critical" ? "var(--status-critical)" : "var(--text-primary)" }}
      >
        {value}
      </div>
      <div className="mt-1 text-sm text-text-secondary">{label}</div>
    </div>
  );
}
