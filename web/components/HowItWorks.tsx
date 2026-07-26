const SIGNALS = [
  {
    title: "Hazard classification history",
    body: "How many severe hazard codes a substance carries under EU CLP: carcinogenicity, aquatic toxicity, reproductive toxicity, and how recently a classification was added.",
  },
  {
    title: "Scientific assessment scrutiny",
    body: "How many EFSA toxicological assessments exist, over what span of years. Sustained scientific attention is itself a signal, whatever each assessment concluded.",
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
    title: "Links to flagged substances",
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
          The model is always compared against trivial baselines, single features ranked on
          their own, on the identical task and split. If it doesn&apos;t beat them, the baseline
          becomes the published result.
        </p>
        <div className="mt-6 rounded-lg border border-status-critical/40 bg-page p-5">
          <h3 className="font-medium text-text-primary">
            One of those baselines beat it
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            For a long time the baselines here were hazard count, sales tonnage and assessment
            count. All three are weak, and the model beat them comfortably. Approval age was
            never tested on its own, because it sat inside the model as a feature.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Ranking substances by nothing but how long they have held EU approval reaches{" "}
            <strong className="text-text-primary">98% of the full model&apos;s average
            precision</strong>, wins outright at 11 of the 16 cutoffs, and reproduces the
            headline lead times exactly: chlorpyrifos at 132 months, thiacloprid at 133,
            clothianidin at 120. Removing the two approval-age features leaves the model at 37%
            of its performance.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The reason is structural. A substance can only be non-renewed when its approval comes
            up for renewal, and approval age proxies proximity to that decision. So the ranking
            is substantially answering <em>whose turn it is</em> rather than <em>who fails</em>.
            That is knowable at the cutoff, so it is not leakage, but it is not the question this
            benchmark was built to ask.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The six evidence groups above are therefore worth, over a date subtraction, one extra
            landmark out of ten and 0.008 average precision. That is the honest measure of what
            the graph adds today, and it is why approval age is now reported as a baseline rather
            than hidden inside the model.
          </p>
        </div>
      </div>
    </section>
  );
}
