const SIGNALS = [
  {
    title: "Hazard classification history",
    body: "How many severe hazard codes a substance carries under EU CLP: carcinogenicity, aquatic toxicity, reproductive toxicity, and how recently a classification was added.",
  },
  {
    title: "Scientific assessment scrutiny",
    body: "How many EFSA toxicological assessments exist, over what span of years. Sustained scientific attention is itself a signal, independent of the conclusion.",
  },
  {
    title: "Sales and usage trends",
    body: "Tonnage sold over time, trend direction, and volatility. A substance quietly losing market share behaves differently from one still expanding.",
  },
  {
    title: "EU regulatory history",
    body: "How long a substance has held EU approval, and its history of renewals or restrictions: the single strongest signal the model has found so far.",
  },
  {
    title: "Graph structure",
    body: "Shared hazard classifications and metabolic degradation links to other substances already flagged as concerning.",
  },
  {
    title: "Independent literature signal",
    body: "How a substance's share of hazard-flavoured scientific literature (Europe PMC) compares to the rest of the field in the same year. This is the one signal here that sits upstream of the regulatory process itself.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          How it decides
        </h2>
        <p className="mt-4 text-text-secondary">
          Every ranking traces back to real, dated, publicly-sourced facts. A
          gradient-boosted model (XGBoost) is trained on six feature groups,
          each grounded in a specific public source:
        </p>
        <div className="mt-8 space-y-5">
          {SIGNALS.map((s) => (
            <div key={s.title} className="border-l-2 border-accent/50 pl-4">
              <h3 className="font-medium text-text-primary">{s.title}</h3>
              <p className="mt-1 text-sm text-text-secondary">{s.body}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-sm text-text-secondary">
          The model is always compared against dead-simple trivial baselines:
          severe-hazard count alone, latest sales tonnage alone, assessment
          count alone, on the identical task and split. If it doesn&apos;t
          beat them, the baseline becomes the published result.
        </p>
      </div>
    </section>
  );
}
