const PRINCIPLES = [
  {
    title: "Temporal integrity",
    body: "Every fact and edge in the graph carries the earliest date it was publicly knowable. Evaluation only ever sees facts dated before the cutoff being tested — the discipline that makes a retrospective claim like “would have flagged it” actually valid, not hindsight dressed up as foresight.",
  },
  {
    title: "The baseline rule",
    body: "No learned model is reported without a trivial baseline run on the identical task and split. A negative result, honestly reported, is a valid outcome — not a reason to keep tuning until something wins.",
  },
  {
    title: "Honesty over novelty",
    body: "Misses are published alongside hits. An early version of this project asked whether Hazium could have flagged a specific 2026 Swedish controversy before it broke — the honest answer was no, with current data, and that negative result is on the record.",
  },
  {
    title: "Evidence paths, not black boxes",
    body: "A ranking is never just a number. Every score traces through the graph to the source documents behind it — an EFSA opinion, an EU regulation, a hazard classification — so a result can be checked, not just trusted.",
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
