import Link from "next/link";
import type { SurvivalData, TfaScreenData, WatchlistData } from "@/lib/types";

/**
 * The landing page's whole argument, in three cards.
 *
 * The page this replaced ran to fourteen screens, which meant a reader deciding
 * in a minute whether to keep going had to scroll past the method to reach any
 * result. These carry the actual numbers rather than teasers, because the depth
 * behind them is the point and a reader who never clicks through should still
 * leave knowing what was found.
 */
export default function Findings({
  survival,
  screen,
  watchlist,
}: {
  survival: SurvivalData;
  screen: TfaScreenData;
  watchlist: WatchlistData;
}) {
  const h1 = survival.horizon_1;
  const age = h1.arms["age only"].average_precision;
  const both = h1.arms["age + evidence"].average_precision;
  const split = h1.quoted_split;
  const decidedBy2027 = watchlist.calendar.find((r) => r.year === 2027)?.cumulative ?? 0;

  return (
    <section id="findings" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          What it found
        </h2>

        <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-3">
          <Card
            href="/method"
            eyebrow="Withdrawal risk"
            figure={`${split?.both_hits_at_50} vs ${split?.age_hits_at_50}`}
            headline="real withdrawals in a forward-tested top 50, against the strongest trivial baseline"
            body={`Fitted on ${split?.train_through} and scored on everything after. Average precision goes from ${age.toFixed(3)} on approval age alone to ${both.toFixed(3)} with the evidence added, at p = ${survival.verification.permutation_p.toFixed(3)} on a block permutation.`}
            cta="How it decides, and what each source is worth"
          />
          <Card
            href="/watchlist#screen"
            eyebrow="PFAS precursors"
            figure={`${screen.flagged} of ${screen.population}`}
            headline={`approved substances that can form TFA, holding all ${screen.kemi_total} Sweden is reevaluating`}
            body={`One rule over a public molecular formula, no model and nothing fitted. Chance would place ${screen.expected_by_chance.toFixed(1)} of the cohort in a shortlist this size.`}
            cta="The whole shortlist"
          />
          <Card
            href="/watchlist"
            eyebrow="Live, and falsifiable"
            figure={`${watchlist.top} substances`}
            headline="ranked for withdrawal, each carrying the date the Commission must decide"
            body={`${decidedBy2027} of the ${watchlist.tracked} tracked reach their approval expiry by the end of 2027, which is when these predictions can be marked right or wrong.`}
            cta="The watchlist and its deadlines"
          />
        </div>

        <p className="mt-8 max-w-3xl text-sm leading-relaxed text-text-secondary">
          The first version of the withdrawal model reported a much larger number. Ranking on
          approval age alone, a single date subtraction with no model, matched it: a slightly higher
          mean average precision, and the headline lead times to the month. Both benchmark versions are
          published.{" "}
          <Link href="/method" className="text-accent underline underline-offset-2">
            What that turned out to mean
          </Link>
          .
        </p>
      </div>
    </section>
  );
}

function Card({
  href,
  eyebrow,
  figure,
  headline,
  body,
  cta,
}: {
  href: string;
  eyebrow: string;
  figure: string;
  headline: string;
  body: string;
  cta: string;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-xl border border-hairline bg-surface p-5 transition-colors hover:border-accent/50"
    >
      <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
        {eyebrow}
      </span>
      <span className="mt-3 tabular-nums text-2xl font-semibold text-text-primary">{figure}</span>
      <span className="mt-1 text-sm leading-snug text-text-secondary">{headline}</span>
      <span className="mt-3 flex-1 text-xs leading-relaxed text-text-muted">{body}</span>
      <span className="mt-4 text-xs text-accent">
        {cta} <span aria-hidden>&rarr;</span>
      </span>
    </Link>
  );
}
