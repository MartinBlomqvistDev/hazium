import Link from "next/link";
import type { SurvivalData } from "@/lib/types";

/**
 * Six feature groups, each described by what it reads rather than by how well it
 * scores. The measured contribution of each is generated rather than written,
 * because an earlier version of this file called EU regulatory history "the
 * single strongest signal the model has found so far" long after that had
 * stopped being true.
 *
 * The narrative this section used to carry, the baseline that beat an earlier
 * model and the reformulation that followed, now opens the landing page. A
 * reference page that retells the story competes with it; this one holds the
 * numbers behind it instead.
 */
const SIGNALS: { key: string; title: string; body: string }[] = [
  {
    key: "efsa",
    title: "Scientific assessment scrutiny",
    body: "How many EFSA toxicological assessments exist, over what span of years. Sustained scientific attention is itself a signal, whatever each assessment concluded.",
  },
  {
    key: "graph",
    title: "Links to flagged substances",
    body: "Shared hazard classifications and metabolic degradation links to other substances already flagged as concerning.",
  },
  {
    key: "sales",
    title: "Sales and usage trends",
    body: "Tonnage sold over time, trend direction, and volatility. A substance quietly losing market share behaves differently from one still expanding.",
  },
  {
    key: "literature",
    title: "Independent literature signal",
    body: "How a substance's share of hazard-flavoured scientific literature (Europe PMC) compares to the rest of the field in the same year. This is the one signal here that sits upstream of the regulatory process itself.",
  },
  {
    key: "clp",
    title: "Hazard classification history",
    body: "How many severe hazard codes a substance carries under EU CLP: carcinogenicity, aquatic toxicity, reproductive toxicity, and how recently a classification was added.",
  },
  {
    key: "clh",
    title: "Classification intentions",
    body: "Whether ECHA has recorded an intention to propose a harmonised classification, and when. A declared intention is the earliest formal sign that a dossier is moving.",
  },
];

export default function HowItWorks({ survival }: { survival: SurvivalData }) {
  const h1 = survival.horizon_1;
  const both = h1.arms["age + evidence"].average_precision;
  const age = h1.arms["age only"].average_precision;
  const split = h1.quoted_split;
  const v = survival.verification;

  return (
    <section id="how" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          What the model reads
        </h2>
        <p className="mt-4 text-text-secondary">
          Every ranking traces back to real, dated, publicly-sourced facts. A
          gradient-boosted model (XGBoost) is trained on six feature groups, each grounded
          in a specific public source:
        </p>
        <div className="mt-8 space-y-5">
          {SIGNALS.map((s) => (
            <div key={s.key} className="border-l-2 border-accent/50 pl-4">
              <h3 className="font-medium text-text-primary">{s.title}</h3>
              <p className="mt-1 text-sm text-text-secondary">{s.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-10">
          <h3 className="font-medium text-text-primary">What each one is worth</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Average precision added when that group alone is given to the model on top of
            approval age. Two groups come out slightly negative. They stay in, because
            dropping a feature after seeing its sign is how a benchmark stops measuring
            anything.
          </p>
          <div className="mt-4 space-y-1.5">
            {SIGNALS.map((s) => {
              const delta = h1.groups[s.key] ?? 0;
              const width = Math.min(100, (Math.abs(delta) / 0.09) * 100);
              const negative = delta < 0;
              return (
                <div key={s.key} className="flex items-center gap-2 text-sm sm:gap-3">
                  <span className="w-24 shrink-0 truncate text-text-secondary sm:w-40">
                    {s.title}
                  </span>
                  <span className="relative h-3 flex-1 rounded-sm bg-hairline/40">
                    <span
                      className="absolute inset-y-0 left-0 rounded-sm"
                      aria-hidden
                      style={{
                        width: `${Math.max(width, negative ? 2 : 0)}%`,
                        backgroundColor: negative
                          ? "var(--status-critical)"
                          : "var(--accent)",
                      }}
                    />
                  </span>
                  <span className="w-16 shrink-0 text-right font-mono text-xs tabular-nums text-text-secondary">
                    {delta >= 0 ? "+" : "−"}
                    {Math.abs(delta).toFixed(3)}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            EFSA assessments and ECHA classification intentions read the regulator&apos;s own
            pipeline, so a result resting on them would be reporting regulatory intent rather
            than anticipating it. Measured as blocks, those two contribute{" "}
            {h1.blocks.in_funnel.toFixed(3)} and the four that sit outside the pipeline
            contribute {h1.blocks.out_of_funnel.toFixed(3)}. The result does not depend on
            reading the regulator.
          </p>
        </div>

        <div className="mt-10">
          <h3 className="font-medium text-text-primary">The checks behind the headline</h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            The reported gain is {age.toFixed(3)} for approval age alone against{" "}
            {both.toFixed(3)} with the evidence added.{" "}
            <Link href="/" className="text-accent underline underline-offset-2">
              Why the question had to be reformulated to get there
            </Link>{" "}
            is on the landing page. These are the checks that number had to survive.
          </p>
          <dl className="mt-4 space-y-2 text-sm">
            {[
              {
                k: "Seed spread",
                v: `the gain is +${(both - age).toFixed(3)} against ±${h1.arms["age + evidence"].seed_sd.toFixed(3)} across seeds`,
              },
              {
                k: "Feature lag",
                v: `reading every feature three years old decays it to +${v.lag_deltas["3"].toFixed(3)} rather than collapsing it`,
              },
              {
                k: "Permutation",
                v: `shuffling whole substance histories puts it at p = ${v.permutation_p.toFixed(3)}`,
              },
              {
                k: "Forward split",
                v: `fitted on ${split?.train_through}, its top 50 holds ${split?.both_hits_at_50} real withdrawals against the baseline's ${split?.age_hits_at_50}`,
              },
            ].map((row) => (
              <div key={row.k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                <dt className="shrink-0 font-medium text-text-primary sm:w-32">{row.k}</dt>
                <dd className="text-text-secondary">{row.v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="mt-10">
          <h3 className="font-medium text-text-primary">And what limits it</h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Measured by the same kind of check rather than estimated.
          </p>
          <dl className="mt-4 space-y-2 text-sm">
            {[
              {
                k: "Interactions",
                v: `a linear model recovers about ${(v.linear_share_recovered * 100).toFixed(0)}% of the gain, so it does not live in any single feature`,
              },
              {
                k: "Calibration",
                v: "raw scores are overconfident and need calibrating before they can be read as probabilities",
              },
              {
                k: "One era",
                v: "most events fall in the 2017 to 2021 renewal wave, and a model fitted before it does not transfer into it",
              },
              {
                k: "Not age-free",
                v: `approval age is about ${(v.age_from_evidence_r2 * 100).toFixed(0)}% recoverable from the evidence, so the evidence-only arm carries some of the calendar`,
              },
            ].map((row) => (
              <div key={row.k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                <dt className="shrink-0 font-medium text-text-primary sm:w-32">{row.k}</dt>
                <dd className="text-text-secondary">{row.v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
