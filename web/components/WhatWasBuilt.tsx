/**
 * A scannable statement of what exists, placed directly under the hero.
 *
 * The rest of the page argues a scientific case at length. A reader deciding in
 * thirty seconds whether to keep going needs the other half of the story first:
 * what was actually built, how it is checked, and what has been published. Those
 * facts were previously only in the repository, which is one click too far.
 *
 * The last item is the one that matters most and reads oddly at first glance. A
 * mapped boundary is a result, and four candidate domains examined and rejected
 * on the evidence is a stronger claim about the method than a fifth domain
 * claimed without one.
 */
const BUILT = [
  {
    figure: "17,133",
    label: "nodes in the temporal graph",
    note: "24,784 edges, every one dated with when it became public",
  },
  {
    figure: "6",
    label: "independent public sources",
    note: "EU Pesticides DB, ECHA CLP, EFSA, KemI, Europe PMC, SGU",
  },
  {
    figure: "374",
    label: "tests, green on every push",
    note: "GitHub Actions, ruff, pytest, pinned toolchain",
  },
  {
    figure: "4",
    label: "candidate domains gated and rejected",
    note: "PFAS, biocides, food additives, feed additives. The boundary is the result",
  },
];

export default function WhatWasBuilt() {
  return (
    <section className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2">
          {BUILT.map((item) => (
            <div key={item.label} className="flex gap-4">
              <span className="w-16 shrink-0 tabular-nums font-mono text-lg text-accent">
                {item.figure}
              </span>
              <span className="min-w-0">
                <span className="block text-sm text-text-primary">{item.label}</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-text-muted">
                  {item.note}
                </span>
              </span>
            </div>
          ))}
        </div>
        <p className="mt-8 text-xs text-text-muted">
          Code is{" "}
          <a
            href="https://github.com/MartinBlomqvistDev/hazium"
            className="text-accent underline underline-offset-2"
          >
            open on GitHub
          </a>{" "}
          under AGPL-3.0. The benchmark is published separately as{" "}
          <a
            href="https://huggingface.co/datasets/MartinBlomqvist/hewb"
            className="text-accent underline underline-offset-2"
          >
            a citable dataset
          </a>{" "}
          under CC-BY-4.0.
        </p>
      </div>
    </section>
  );
}
