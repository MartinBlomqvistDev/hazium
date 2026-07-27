import type { AnchorCohort, TfaScreenData } from "@/lib/types";

/**
 * The measurement, and only the measurement.
 *
 * This block used to carry the fluazinam story, a side-by-side of the two
 * instruments, and an explanation of TFA chemistry. All three now live on the
 * landing page, which is where a reader meets them first. Repeating them here
 * was how "0 of 6" and "6 of 6" ended up a screen apart with no shared frame.
 *
 * What is left is the part that belongs on a data page: where the regulator's
 * cohort actually landed, against what chance would have done. `expected_in_top_k`
 * never leaves `hits_in_top_k`, because a hit count means nothing without it.
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
          The cohort test
        </h2>
        <p className="mt-4 text-text-secondary">
          On 20 November 2025 Kemikalieinspektionen opened a reevaluation of{" "}
          {cohort.size} plant protection substances that break down into the PFAS
          compound TFA and reach groundwater. Those {cohort.size} were chosen by a
          regulator, on a dated public decision, which is what makes them a test rather
          than an anecdote: asked of one substance, any ranking puts it somewhere and the
          answer can be read either way.
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

        <p className="mt-6 text-sm leading-relaxed text-text-secondary">
          <strong className="text-text-primary">
            {cohort.hits_in_top_k} of {cohort.size}
          </strong>{" "}
          reach that band, where a random draw would have placed{" "}
          {cohort.expected_in_top_k.toFixed(1)}. The median sits at the{" "}
          {Math.round(cohort.median_percentile * 100)}th percentile, so this is not a near
          miss. The withdrawal model does not find them.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          The structural screen, over the same population and answering the other
          question, holds all {screen.kemi_total} of them.{" "}
          <a href="#screen" className="text-accent underline underline-offset-2">
            Its shortlist is below
          </a>
          , with this cohort held out as its check.
        </p>
      </div>
    </section>
  );
}
