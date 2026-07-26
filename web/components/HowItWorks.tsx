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
            One of those baselines beat it, and fixing that is the result
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            For a long time the baselines here were hazard count, sales tonnage and assessment
            count. All three are weak, and the model beat them comfortably. Approval age was
            never tested on its own, because it sat inside the model as a feature.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Ranking on nothing but how long a substance has held EU approval reaches{" "}
            <strong className="text-text-primary">98% of the full model</strong> and reproduces
            the lead times above exactly: chlorpyrifos at 132 months, thiacloprid at 133,
            clothianidin at 120. A date subtraction, no model at all.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The cause turned out to be the question rather than the data. &ldquo;Was this ever
            withdrawn&rdquo; is asked over a population that is 96% substances never approved in
            the EU, which could never be withdrawn at all. Answering it is mostly an eligibility
            test, and approval age performs that test.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Asked separably, one approved substance in one year at risk, approval age becomes the
            background rate and the evidence has something left to explain. It does:{" "}
            <strong className="text-text-primary">0.102 for age alone against 0.253 for age plus
            evidence</strong>, a gain of +0.151 against a seed spread of 0.032. Approval age is
            not recoverable from the evidence (R&sup2; = &minus;0.009), the signal survives
            lagging every feature three years, a block permutation puts it at p = 0.024, and in a
            forward split fit on 2019 the top 50 holds 15 real withdrawals against age&apos;s 4.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The limits are measured too. A linear model recovers a fifth of it, so it lives in
            interactions; the raw scores are overconfident and need calibrating before they can
            be read as probabilities; and 75 of 102 events fall in the 2017&ndash;2021 renewal
            wave, which is the real constraint: a model fitted before that wave does not
            transfer into it. Both
            benchmark versions are published:{" "}
            <a
              href="https://github.com/MartinBlomqvistDev/hazium/tree/main/release/hewb-v2"
              className="text-accent underline underline-offset-2"
            >
              HEWB v2
            </a>{" "}
            alongside the frozen v1.4, because reading them together is the point.
          </p>
        </div>
      </div>
    </section>
  );
}
