import type { SurvivalData, TfaScreenData } from "@/lib/types";

/**
 * The hero once led with 7/10 landmark bans and a 132-month lead time. Both are
 * real and both are reproducible by subtracting two dates, which the page went
 * on to say five screens later, so it opened with a claim it then argued against.
 *
 * The three that replaced them are ordered for the reader who arrives first,
 * which for a portfolio site is usually a recruiter rather than a modeller. Two
 * of them can be understood with no background at all; average precision cannot,
 * so it goes last rather than first. A version badge used to sit above the
 * headline and was the first thing anyone read, which spent the opening on an
 * internal acronym.
 */
export default function Hero({
  survival,
  screen,
}: {
  survival: SurvivalData;
  screen: TfaScreenData;
}) {
  const h1 = survival.horizon_1;
  const age = h1.arms["age only"].average_precision;
  const both = h1.arms["age + evidence"].average_precision;
  const split = h1.quoted_split;

  return (
    <section id="top" className="border-b border-hairline">
      <div className="mx-auto max-w-5xl px-6 py-20 sm:py-28">
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Can public evidence tell you{" "}
          <span className="text-accent">which pesticide falls next?</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-text-secondary">
          Hazium joins public EU and Swedish records about pesticides into one graph,
          then works out which ones are heading for trouble. Every fact carries the
          date it became public, so nothing a model sees is something it could not
          have known at the time.
        </p>
        <p className="mt-4 max-w-2xl text-text-secondary">
          Partly. One thing predicts a withdrawal with no model at all: how long
          a substance has held approval. What counts is how far the evidence gets
          past that.
        </p>

        {/* Ordered for the first reader, who is often a recruiter rather than a
            modeller. The two self-explanatory results lead; average precision,
            which means nothing without ML background, comes last. */}
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Stat
            value={`${screen.flagged} of ${screen.population}`}
            label={`pesticides approved in the EU that break down into PFAS, found from molecular structure alone. All ${screen.kemi_total} that Sweden is now reevaluating are among them.`}
          />
          {split && (
            <Stat
              value={`${split.both_hits_at_50} vs ${split.age_hits_at_50}`}
              label={`real EU withdrawals caught in a 50-substance shortlist, against 4 for the strongest simple rule. Trained on data up to ${split.train_through}, then tested on what happened after.`}
            />
          )}
          <Stat
            value={`${age.toFixed(2)} → ${both.toFixed(2)}`}
            label="average precision on that ranking task, from approval age alone to age plus the evidence"
          />
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
