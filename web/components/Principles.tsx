/**
 * Three, not five.
 *
 * The two that went, temporal integrity and evidence paths, are real and are
 * demonstrated elsewhere on the site by the dated mesh and the click-through to
 * source documents. Stating them here as well was asking to be believed about
 * something a reader can already see working. These three are the ones that
 * cannot be shown in a visual and would otherwise go unsaid.
 */
const PRINCIPLES = [
  {
    title: "The baseline rule",
    body: "No learned model is reported without a trivial baseline on the identical task and split. When the baseline wins, it becomes the published result. One did.",
  },
  {
    title: "The misses are published too",
    body: "Every version records which landmarks it fails to flag, and every superseded version stays online with the results that led to it. The hazard this project was built for is one the model does not find, and that measurement has a section of its own.",
  },
  {
    title: "Cohorts, not anecdotes",
    body: "A single substance in a favourable position is not evidence. Where a claim can be tested against a group someone else defined, on a date they published, that is the group reported, whichever way it comes out.",
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
