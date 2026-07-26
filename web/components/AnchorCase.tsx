import type { AnchorCohort, TfaScreenData } from "@/lib/types";

/**
 * The result the project would most like to have gone the other way.
 *
 * Fluazinam is the reason Hazium exists, so "where does it rank" is the first
 * question a reader asks. Asked of one substance it cannot be answered: any
 * ranking puts something somewhere, and at an earlier stage of this work
 * fluazinam sat at 96 of 260, inside the published band, which reads as a hit
 * until the rest of its cohort is put beside it.
 *
 * Kemikalieinspektionen named six TFA-forming substances on the same day. That
 * set is dated, externally defined, and chosen by a regulator rather than by
 * this project, so it can be used as a test. It is reported here whatever it
 * says, and it says the model does not find them.
 */
export default function AnchorCase({
  cohort,
  screen,
}: {
  cohort: AnchorCohort;
  screen: TfaScreenData;
}) {
  const ranked = Object.entries(cohort.ranks).sort((a, b) => a[1] - b[1]);
  const worst = Math.max(...ranked.map(([, r]) => r), cohort.population);

  return (
    <section id="anchor" className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          The case it still misses
        </h2>
        <p className="mt-4 text-text-secondary">
          Everything above is measured against EU withdrawals. This is measured against the
          hazard the project was built for, and the model does not find it.
        </p>
        <p className="mt-4 text-text-secondary">
          On 20 November 2025 Kemikalieinspektionen opened a reevaluation of six plant
          protection substances that break down into the PFAS compound TFA and reach
          groundwater. Fluazinam is one of them. Those six were chosen by a regulator, on a
          dated public decision, which is what makes them a test rather than an anecdote.
        </p>

        <div className="mt-8 rounded-xl border border-hairline bg-surface p-5 sm:p-7">
          <div className="flex items-baseline justify-between text-xs text-text-muted">
            <span>most concerning</span>
            <span>rank of {cohort.population} approved substances</span>
          </div>
          <div className="mt-4 space-y-2">
            {ranked.map(([sid, rank]) => (
              <div key={sid} className="flex items-center gap-2 text-sm sm:gap-3">
                <span className="w-28 shrink-0 truncate text-text-secondary sm:w-40">
                  {cohort.names[sid] ?? sid}
                </span>
                <span className="relative h-3 flex-1 rounded-sm bg-hairline/40">
                  {/* The published band, drawn so the gap to it is the message. */}
                  <span
                    className="absolute inset-y-0 left-0 rounded-sm"
                    aria-hidden
                    style={{
                      width: `${(cohort.top_k / worst) * 100}%`,
                      background: "var(--accent)",
                      opacity: 0.16,
                    }}
                  />
                  <span
                    className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[1px]"
                    aria-hidden
                    style={{
                      left: `${(rank / worst) * 100}%`,
                      background: "var(--status-critical)",
                    }}
                  />
                </span>
                <span className="w-10 shrink-0 text-right font-mono text-xs tabular-nums text-text-secondary">
                  {rank}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-text-muted">
            The shaded band is the published top {cohort.top_k}.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Stat
            value={`${cohort.hits_in_top_k} of ${cohort.size}`}
            label={`in the published top ${cohort.top_k}`}
          />
          <Stat
            value={cohort.expected_in_top_k.toFixed(1)}
            label="how many chance alone would put there"
          />
          <Stat
            value={`${Math.round(cohort.median_percentile * 100)}%`}
            label="cohort median position, where chance is 50%"
          />
        </div>

        <p className="mt-8 text-sm leading-relaxed text-text-secondary">
          Not one of them reaches the band, where a random draw would put{" "}
          {cohort.expected_in_top_k.toFixed(1)}. The cohort sits slightly worse than chance.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          TFA is a degradation product, and the hazard shows up in groundwater monitoring,
          which is not among the sources feeding Hazium. Nothing in an approval record, a
          hazard classification or a sales table says that a substance becomes something
          persistent after it leaves the field. The regulatory record cannot carry this
          signal, so a model over the regulatory record cannot find it.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          The molecule carries it instead. TFA comes from trifluoromethyl groups, and a
          formula is public, unchanging and knowable at every cutoff. Screening the same{" "}
          {screen.population} approved substances on structure alone narrows them to{" "}
          <strong className="text-text-primary">
            {screen.flagged}, and all six are among them
          </strong>
          . That is chemistry rather than machine learning, which is the finding: the right
          tool followed from asking what the hazard actually was.{" "}
          <a href="#screen" className="text-accent underline underline-offset-2">
            The whole shortlist is below
          </a>
          , with the cohort held out as its check.
        </p>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <div className="tabular-nums text-2xl font-semibold text-text-primary">{value}</div>
      <div className="mt-1 text-xs leading-relaxed text-text-secondary">{label}</div>
    </div>
  );
}
