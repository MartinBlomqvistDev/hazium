/**
 * The human reason the project exists, in two paragraphs.
 *
 * It ran to four. The one that went said that Europe's evidence is split across
 * agencies with no shared schema or identifier, which is true and which every
 * data-integration project on the internet also says. The fluazinam case makes
 * the same point concretely, so the abstract version was costing a screen and
 * earning nothing.
 */
export default function OriginStory() {
  return (
    <section className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-14">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Why this exists
        </h2>
        <p className="mt-4 text-xl leading-relaxed text-text-primary">
          Hazium began with a simple question: could publicly available data
          have revealed a Swedish pesticide controversy before it became
          national news?
        </p>
        <p className="mt-4 leading-relaxed text-text-secondary">
          No, and the reason is precise. Fluazinam&apos;s real concern is groundwater: it
          breaks down into the PFAS compound TFA. Kemikalieinspektionen opened a formal
          reevaluation in November 2025 and an SVT investigation made it national news in
          July 2026, but nothing in the EU approval records, hazard classifications,
          literature or sales figures this project reads mentions any of that.{" "}
          <a href="/watchlist#anchor" className="text-accent underline underline-offset-2">
            The miss is measured
          </a>{" "}
          against the whole cohort the regulator named rather than fluazinam alone, and a
          screen over molecular structure does find them.
        </p>
        <p className="mt-4 leading-relaxed text-text-secondary">
          The concern is not in doubt. A national SGU groundwater investigation across 2023
          to 2025 found TFA at{" "}
          <strong className="text-text-primary">91 percent of the sites it tested</strong>,
          while Sweden&apos;s pesticide monitoring has never once detected fluazinam itself:
          the parent does not arrive, because by then it is TFA. That monitoring is too
          recent to have fed any historical ranking, so it is not a model input. It is
          after-the-fact confirmation of exactly the thing the project set out to catch,
          and folding it in is the next step.
        </p>
      </div>
    </section>
  );
}
