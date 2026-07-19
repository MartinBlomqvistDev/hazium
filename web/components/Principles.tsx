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
    title: "Honesty over novelty",
    body: "HEWB publishes the misses next to the hits. Every version records which landmarks it fails to flag before their real regulatory action.",
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
