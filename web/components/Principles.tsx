const PRINCIPLES = [
  {
    title: "Temporal integrity",
    body: "Every fact and edge carries the earliest date it was publicly knowable, and evaluation sees only facts dated before the cutoff being tested. A claim like “would have flagged it” is measured against what the model could actually have known at the time.",
  },
  {
    title: "The baseline rule",
    body: "No learned model is reported without a trivial baseline on the identical task and split. When the baseline wins, it becomes the published result.",
  },
  {
    title: "The misses are published too",
    body: "Every version of HEWB records which landmarks it fails to flag, and every superseded version stays online with the results that led to it. Both are on this page, including the hazard the project was built for and does not find.",
  },
  {
    title: "Cohorts, not anecdotes",
    body: "A single substance in a favourable position is not evidence. Where a claim can be tested against a group someone else defined, on a date they published, that is the group reported, whichever way it comes out.",
  },
  {
    title: "Evidence paths",
    body: "A ranking is more than a number. Every score traces through the graph to the documents behind it: an EFSA opinion, an EU regulation, a hazard classification, each one a reader can open and check.",
  },
];

export default function Principles() {
  return (
    <section id="principles" className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Principles
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2">
          {PRINCIPLES.map((p) => (
            <div key={p.title}>
              <h3 className="font-medium text-text-primary">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{p.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
