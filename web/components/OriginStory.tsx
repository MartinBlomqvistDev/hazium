export default function OriginStory() {
  return (
    <section className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Why this exists
        </h2>
        <p className="mt-4 text-xl leading-relaxed text-text-primary">
          Hazium began with a simple question: could publicly available data
          have revealed a Swedish pesticide controversy before it became
          national news?
        </p>
        <p className="mt-4 leading-relaxed text-text-secondary">
          The answer was no, and the reason is precise. Fluazinam&apos;s actual
          concern is groundwater: it breaks down into the PFAS substance
          trifluoroacetic acid (TFA), which spreads to groundwater.
          Kemikalieinspektionen opened a formal reevaluation in November 2025,
          and an SVT investigation made it national news in July 2026. The
          sources ingested so far, EU regulatory
          history, EU hazard classifications, and Swedish sales, do not cover
          groundwater or residue monitoring, so that specific signal sits outside
          the current data.
        </p>
        <p className="mt-4 leading-relaxed text-text-secondary">
          The concern itself is not in doubt. A national SGU groundwater
          investigation across 2023 to 2025 found TFA at 91 percent of 237 sites
          (median 230 ng/l), tied to fluorinated plant-protection products
          breaking down. Sweden&apos;s historical pesticide monitoring meanwhile
          records fluazinam at zero of 139 groundwater analyses: the parent
          never arrives because it becomes TFA. That monitoring is too recent to
          have fed a pre-2023 ranking, so it is not a model input; it is
          independent, after-the-fact confirmation of the concern the project set
          out to anticipate. Folding groundwater and residue monitoring in as a
          present-day signal is the next step on the roadmap.
        </p>
        <p className="mt-4 leading-relaxed text-text-secondary">
          That gap is the real origin of the project. Environmental and
          public health evidence exists in volume across Europe: regulatory
          decisions, hazard classifications, sales statistics, scientific
          literature. It is split across agencies that do not share a
          schema, a timeline, or even a common substance identifier. Hazium
          joins that evidence into one temporally dated graph, so a ranking
          can be checked against what was knowable at a real cutoff.
        </p>
      </div>
    </section>
  );
}
