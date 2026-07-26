import type { WatchlistData } from "@/lib/types";

const ACCENT = "#d95926";
const INK_MUTED = "#898781";

/**
 * The one forward-looking surface on the site.
 *
 * Two presentation decisions here are deliberate rather than stylistic. The
 * crop bars are drawn against a base-rate marker, because without it a reader
 * sees "wheat 40%" and concludes wheat is singled out. Measured against the
 * rate across all crop-bearing products, the cereals are about 1.1x and every
 * other crop sits below, a real gradient but a shallow one. And no product or
 * brand is named anywhere: the crop is the finest granularity published,
 * because a large share of any list this length is never actioned.
 */
export default function Watchlist({ data }: { data: WatchlistData }) {
  const soon = data.calendar.filter((row) => row.year <= 2028);
  const decidedBy2027 = data.calendar.find((row) => row.year === 2027)?.cumulative ?? 0;
  const maxCount = Math.max(...data.calendar.map((r) => r.count), 1);
  const maxPercent = Math.max(...data.crops.map((c) => c.percent), 1);
  const byVolume = data.entries
    .filter((e) => e.tonnes !== null)
    .sort((a, b) => (b.tonnes ?? 0) - (a.tonnes ?? 0))
    .slice(0, 10);

  return (
    <section id="watchlist" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          What it says next
        </h2>
        <p className="mt-4 text-text-secondary">
          Everything above is retrospective: the model is graded against bans that already
          happened. This is the opposite, and it carries a different status. These are
          substances the model ranks as concerning today, and{" "}
          <strong className="text-text-primary">none of them has been checked against
          anything</strong>, because the future they concern has not happened. What makes it
          falsifiable anyway is that every EU approval carries an expiry date, and on that date
          the Commission has to decide. Each entry comes with its own deadline.
        </p>
        <p className="mt-4 text-sm text-text-secondary">
          The ranking is a modelled three-year hazard among substances currently approved and not
          yet withdrawn, not the &ldquo;will this ever be withdrawn&rdquo; score used earlier. That
          older target was answered largely by approval age, so it mostly returned old approvals.
          Under this one, approval age is the baseline rate and the evidence does the
          discriminating: the two substances that most obviously did not belong near the top, a
          fatty-acid soap and acetic acid, fall from 5th and 62nd to 27th and 192nd.
        </p>

        <div className="mt-10">
          <h3 className="font-medium text-text-primary">When this gets marked</h3>
          <p className="mt-2 text-sm text-text-secondary">
            {decidedBy2027} of {data.tracked} tracked substances reach their approval expiry by
            the end of 2027.
          </p>
          <div className="mt-5 space-y-2">
            {soon.map((row) => (
              <div key={row.year} className="flex items-center gap-2 text-sm sm:gap-3">
                <span className="w-11 shrink-0 tabular-nums font-mono text-text-secondary">
                  {row.year}
                </span>
                <span className="h-3 shrink-0 rounded-sm" aria-hidden
                  style={{ width: `${(row.count / maxCount) * 45}%`, backgroundColor: ACCENT }} />
                <span className="tabular-nums text-text-secondary">
                  {row.count} decided
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            An expiry passing is not automatically a verdict: the Commission often extends an
            approval by a short procedural step while an assessment finishes. Those are recorded
            as still open rather than counted either way.
          </p>
        </div>

        <div className="mt-12">
          <h3 className="font-medium text-text-primary">
            Which crops they are approved for
          </h3>
          <p className="mt-2 text-sm text-text-secondary">
            {data.on_market} of the top {data.top} are in plant protection products currently
            approved in Sweden. The bars show the share of each crop&apos;s{" "}
            <strong className="text-text-primary">approved products</strong> carrying at least
            one of them.
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            This is the catalogue, not the fields: what a grower could legally buy, not what was
            sprayed or on what area.
          </p>
          <div className="mt-5 space-y-1.5">
            {data.crops.slice(0, 14).map((crop) => (
              <div key={crop.crop} className="flex items-center gap-2 text-sm sm:gap-3">
                <span className="w-20 shrink-0 truncate text-text-secondary sm:w-28">
                  {crop.crop}
                </span>
                <span className="relative h-3 w-[34%] shrink-0 rounded-sm bg-hairline/40 sm:w-[45%]">
                  <span className="absolute inset-y-0 left-0 rounded-sm" aria-hidden
                    style={{ width: `${(crop.percent / maxPercent) * 100}%`, backgroundColor: ACCENT }} />
                  <span className="absolute inset-y-[-3px] w-px" aria-hidden
                    style={{
                      left: `${(data.base_rate_percent / maxPercent) * 100}%`,
                      backgroundColor: INK_MUTED,
                    }} />
                </span>
                <span className="tabular-nums font-mono text-xs text-text-secondary">
                  {crop.percent}%
                </span>
                <span className="hidden tabular-nums font-mono text-xs text-text-muted sm:inline">
                  {crop.flagged}/{crop.products}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            The grey line marks {data.base_rate_percent}%, the share across every approved
            product that names a crop. Read the bars against it rather than against each other.
            The cereals sit a little above it and most other crops below, but the whole range is
            roughly two thirds to one and a sixth of that rate, so the finding is that these
            substances are spread across Swedish agriculture rather than concentrated anywhere.
          </p>
        </div>

        <div className="mt-12">
          <h3 className="font-medium text-text-primary">How much is actually sold</h3>
          <p className="mt-2 text-sm text-text-secondary">
            {data.with_sales} of them have recorded Swedish sales. Tonnage alone is unreadable,
            because the median plant protection active sells 0.2 tonnes a year here while the
            largest sells 783, so each is shown with its rank among the {data.sales_ranked}{" "}
            actives sold in {data.sales_year}.
          </p>
          <div className="mt-5 space-y-1.5">
            {byVolume.map((entry) => (
              <div key={entry.name} className="flex items-center gap-2 text-sm sm:gap-3">
                <span className="w-32 shrink-0 truncate text-text-secondary sm:w-44">
                  {entry.name}
                </span>
                <span className="w-16 shrink-0 tabular-nums text-right font-mono text-xs text-text-secondary">
                  {entry.tonnes} t
                </span>
                <span className="tabular-nums font-mono text-xs text-text-muted">
                  #{entry.sales_rank}
                </span>
                <span className="hidden truncate text-xs text-text-muted sm:inline">
                  {entry.crops.slice(0, 3).join(", ")}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            National tonnage, not tonnage per crop, because nobody publishes the second in a form
            that joins to a substance ranking. Sweden&apos;s per-crop survey reports by pesticide
            type rather than by substance and was last run for 2021; Eurostat states it has never
            been able to publish comparable EU use statistics at all. A fix was legislated in
            2025, with publication from 2030. Until then the honest unit is the country.
          </p>
        </div>

        <p className="mt-10 text-xs leading-relaxed text-text-muted">
          No product or brand is named, and none will be. At the cutoffs old enough to have
          resolved, a little under half of a top-100 band was never actioned, so naming
          commercial products against it would put specific companies on a list carrying that
          much error. Crop is the finest granularity published. Generated {data.generated}.
        </p>
      </div>
    </section>
  );
}
