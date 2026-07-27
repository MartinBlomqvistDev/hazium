"use client";

import { useState } from "react";
import type { WatchlistData, WatchlistEntry } from "@/lib/types";

const ACCENT = "#d95926";

/** Crops listed in the bar chart. The caption below it derives from the same slice. */
const CROPS_SHOWN = 14;
const INK_MUTED = "#898781";

/** The Commission's own record for an active substance, keyed by its register id. */
function euRecordUrl(id: number): string {
  return `https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/start/screen/active-substances/details/${id}`;
}

/**
 * The one forward-looking surface on the site.
 *
 * Two presentation decisions here are deliberate rather than stylistic. The
 * crop bars are drawn against a base-rate marker, because without it a reader
 * sees "wheat 40%" and concludes wheat is singled out; measured against the
 * rate across all crop-bearing products the whole range is shallow. The caption
 * derives those extremes from the data rather than naming them, since the
 * ranking changes and a hand-written extreme goes stale silently. And no
 * product or brand is named anywhere: the crop is the finest granularity
 * published, because a large share of any list this length is never actioned.
 */
export default function Watchlist({ data }: { data: WatchlistData }) {
  const [open, setOpen] = useState<string | null>(null);
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
            {decidedBy2027} of them reach their approval expiry by the end of 2027, which is
            when the Commission has to decide.
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
            {data.on_market}{" "}
            of them are in plant protection products currently approved in Sweden. Each bar is the share of that crop&apos;s{" "}
            <strong className="text-text-primary">approved products</strong> carrying at least
            one.
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            This is the catalogue, not the fields: what a grower could legally buy, not what was
            sprayed or on what area.
          </p>
          <div className="mt-5 space-y-1.5">
            {data.crops.slice(0, CROPS_SHOWN).map((crop) => (
              <div key={crop.crop} className="flex items-center gap-2 text-sm sm:gap-3">
                <span className="w-20 shrink-0 truncate text-text-secondary sm:w-28">
                  {crop.crop}
                </span>
                <span className="relative h-3 w-[34%] shrink-0 rounded-sm bg-hairline/40 sm:w-[45%]">
                  {/* A measured zero gets a stub rather than an empty track, so it
                      reads as none of them rather than as a bar that failed to draw. */}
                  <span className="absolute inset-y-0 left-0 rounded-sm" aria-hidden
                    style={{
                      width: crop.percent === 0 ? "2px" : `${(crop.percent / maxPercent) * 100}%`,
                      backgroundColor: crop.percent === 0 ? INK_MUTED : ACCENT,
                    }} />
                  <span className="absolute inset-y-[-3px] w-px" aria-hidden
                    style={{
                      left: `${(data.base_rate_percent / maxPercent) * 100}%`,
                      backgroundColor: INK_MUTED,
                    }} />
                </span>
                <span className="w-10 shrink-0 text-right font-mono text-xs tabular-nums text-text-secondary">
                  {crop.percent}%
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            {(() => {
              // The numbers are the referents here. An earlier pass cut them for
              // density and left "the rate" and "twice that rate in either
              // direction", which name nothing and cannot be true downward.
              const shown = data.crops.slice(0, CROPS_SHOWN);
              const low = shown.reduce((a, b) => (b.percent < a.percent ? b : a));
              const high = shown.reduce((a, b) => (b.percent > a.percent ? b : a));
              return (
                <>
                  The grey line sits at {data.base_rate_percent}%, which is the same share
                  measured across every approved product in Sweden that names a crop. It is the
                  level to read each bar against. They run from {low.percent}% for {low.crop} to{" "}
                  {high.percent}% for {high.crop}, a narrow band around that line, so these
                  substances are spread across Swedish agriculture rather than concentrated in
                  any one crop.
                </>
              );
            })()}
          </p>
        </div>

        <div className="mt-12">
          <h3 className="font-medium text-text-primary">How much is actually sold</h3>
          <p className="mt-2 text-sm text-text-secondary">
            {data.with_sales} of them have recorded Swedish sales. Tonnage alone is unreadable,
            because sales are skewed across three orders of magnitude, so each carries its rank
            among every plant protection active sold here in {data.sales_year}.
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Click a substance for its deadline, its full crop list and the Commission&apos;s own
            record.
          </p>
          <div className="mt-4 space-y-1">
            {byVolume.map((entry) => (
              <SalesRow
                key={entry.name}
                entry={entry}
                top={data.top}
                salesRanked={data.sales_ranked}
                salesYear={data.sales_year}
                open={open === entry.name}
                onToggle={() => setOpen(open === entry.name ? null : entry.name)}
              />
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            National tonnage, not tonnage per crop, because nobody publishes the second in a form
            that joins to a substance ranking. Sweden&apos;s per-crop survey reports by pesticide
            type rather than by substance and was last run for 2021; Eurostat states it has never
            been able to publish comparable EU use statistics at all. A fix was legislated in
            2025, with publication from 2030. Until then the country is the finest unit
            available.
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

/**
 * A sales row that opens into what the reader would otherwise have to go and
 * look up: the deadline, the full crop list, and a link to the Commission's own
 * record. Approval age is shown next to the model rank deliberately, because
 * approval age is the baseline hazard this model is measured against, and a
 * reader entitled to the rank is entitled to the number it has to beat.
 */
function SalesRow({
  entry,
  top,
  salesRanked,
  salesYear,
  open,
  onToggle,
}: {
  entry: WatchlistEntry;
  top: number;
  salesRanked: number;
  salesYear: number;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={`rounded-md ${open ? "bg-surface-raised/50" : ""}`}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1.5 text-sm transition-colors hover:bg-surface-raised/60 sm:gap-3"
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <span className="min-w-0 flex-1 truncate text-text-secondary">
          {entry.name}{" "}
          <span className="text-text-muted" aria-hidden>
            {open ? "▾" : "▸"}
          </span>
        </span>
        <span className="w-16 shrink-0 text-right font-mono text-xs tabular-nums text-text-secondary">
          {entry.tonnes} t
        </span>
        <span className="w-8 shrink-0 font-mono text-xs tabular-nums text-text-muted">
          #{entry.sales_rank}
        </span>
        <span className="hidden w-40 shrink-0 truncate text-xs text-text-muted sm:inline">
          {entry.crops.slice(0, 3).join(", ")}
        </span>
      </div>

      {open && (
        <div className="mx-1 mb-2 rounded-md border border-hairline bg-page/60 px-4 py-4 text-xs">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-sm font-medium text-text-primary">{entry.name}</span>
            <span className="text-text-muted">CAS {entry.cas}</span>
          </div>

          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-text-muted">Model rank</dt>
            <dd className="text-text-secondary">
              {entry.rank} of {top}, by modelled three-year hazard
            </dd>

            <dt className="text-text-muted">EU approval held</dt>
            <dd className="text-text-secondary">
              {entry.approval_years === null
                ? "not recorded"
                : `${entry.approval_years} years, the baseline this rank has to beat`}
            </dd>

            <dt className="text-text-muted">Decision due</dt>
            <dd className="text-text-secondary">
              {entry.expiry ?? "no dated expiry, approval is open-ended"}
              {entry.expiry && entry.outcome === "pending" ? ", still open" : ""}
            </dd>

            <dt className="text-text-muted">Sold in Sweden</dt>
            <dd className="text-text-secondary">
              {entry.tonnes} tonnes in {salesYear}, ranked {entry.sales_rank} of {salesRanked}{" "}
              plant protection actives
            </dd>

            <dt className="text-text-muted">Approved for</dt>
            <dd className="text-text-secondary">
              {entry.crops.length ? entry.crops.join(", ") : "no Swedish crop use recorded"}
            </dd>
          </dl>

          {entry.eu_id !== null && (
            <p className="mt-3 border-t border-hairline pt-3">
              <a
                href={euRecordUrl(entry.eu_id)}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                Commission record for this substance
              </a>
              <span className="text-text-muted"> (EU Pesticides Database)</span>
            </p>
          )}

          <p className="mt-3 leading-relaxed text-text-muted">
            Being here is a modelled expectation, not a finding. Most of a band this size is
            never actioned, and this substance is on the list because a model ranked it, not
            because a regulator has said anything about it.
          </p>
        </div>
      )}
    </div>
  );
}
