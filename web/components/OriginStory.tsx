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
          concern is a national groundwater contamination finding involving
          trifluoroacetic acid (TFA), raised by a November 2025 Swedish
          reevaluation and the public controversy that followed in 2026. The
          sources ingested so far, EU regulatory
          history, EU hazard classifications, and Swedish sales, do not cover
          groundwater or residue monitoring, so that specific signal sits outside
          the current data. Bringing residue and groundwater monitoring into the
          graph is the next data source on the roadmap.
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
