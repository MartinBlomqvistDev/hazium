import Link from "next/link";
import type { TfaScreenData, WatchlistData } from "@/lib/types";

/**
 * Three ways into the detail, and deliberately not a second set of headline
 * numbers.
 *
 * This block used to restate the hero's three figures with more decimal places,
 * so a reader met the same result twice in two screens and could not tell
 * whether the second was a new finding. The hero owns the numbers because it
 * sits above the fold. This owns the routes.
 */
export default function Findings({
  screen,
  watchlist,
}: {
  screen: TfaScreenData;
  watchlist: WatchlistData;
}) {
  const decidedBy2027 = watchlist.calendar.find((r) => r.year === 2027)?.cumulative ?? 0;

  const routes = [
    {
      href: "/watchlist",
      title: "What it says about today",
      body: `Every approved pesticide it ranks as concerning, each carrying the date the Commission must decide. ${decidedBy2027} of them fall due by the end of 2027, which is when these predictions can be marked right or wrong.`,
      cta: "See the watchlist",
    },
    {
      href: "/watchlist#screen",
      title: "The PFAS shortlist",
      body: `The ${screen.flagged} substances that can break down into PFAS, with the formula and the Swedish crop uses behind each one. No model: one rule over a public molecular structure.`,
      cta: "See the shortlist",
    },
    {
      href: "/method",
      title: "How it decides, and what beat it",
      body: "The six evidence sources and what each is measurably worth, the verification that survived, and the trivial baseline that matched an earlier version of this model outright.",
      cta: "See the method",
    },
  ];

  return (
    <section id="findings" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-5xl px-6 py-14">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Where to go from here
        </h2>
        <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-3">
          {routes.map((r) => (
            <Link
              key={r.href}
              href={r.href}
              className="group flex flex-col rounded-xl border border-hairline bg-surface p-5 transition-colors hover:border-accent/50"
            >
              <span className="font-medium text-text-primary">{r.title}</span>
              <span className="mt-2 flex-1 text-sm leading-relaxed text-text-secondary">
                {r.body}
              </span>
              <span className="mt-4 text-xs text-accent">
                {r.cta} <span aria-hidden>&rarr;</span>
              </span>
            </Link>
          ))}
        </div>
        <p className="mt-6 max-w-3xl text-sm leading-relaxed text-text-secondary">
          An earlier version of the withdrawal model reported a far larger result. Ranking on
          approval age alone, one date subtraction with no model at all, matched it. Both
          benchmark versions stay published, and{" "}
          <Link href="/method" className="text-accent underline underline-offset-2">
            the method page says what that turned out to mean
          </Link>
          .
        </p>
      </div>
    </section>
  );
}
