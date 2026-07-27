import type { BuildFacts } from "@/lib/types";

/**
 * A scannable statement of what exists, placed directly under the hero.
 *
 * The rest of the page argues a scientific case at length. A reader deciding in
 * thirty seconds whether to keep going needs the other half of the story first:
 * what was actually built, how it is checked, and what has been published.
 *
 * Every figure here is read from `pipeline/36`. Three of them were typed into
 * this file once and all three drifted: the graph grew, a source was added, and
 * the test count moved twice while the page kept claiming an older one.
 */
export default function WhatWasBuilt({ facts }: { facts: BuildFacts }) {
  const built = [
    {
      figure: facts.graph_nodes.toLocaleString("en-GB"),
      label: "nodes in the temporal graph",
      note: `${facts.graph_edges.toLocaleString("en-GB")} edges, every one dated with when it became public`,
    },
    {
      figure: String(facts.model_sources.length),
      label: "public sources feeding the model",
      note: facts.model_sources.join(", "),
    },
    {
      figure: String(facts.tests),
      label: "tests, green on every push",
      note: "GitHub Actions, ruff, pytest, pinned toolchain",
    },
    {
      figure: String(facts.gated_domains.length),
      label: "candidate domains examined and rejected",
      // Named carefully: PFAS failed as a *domain* for the withdrawal model,
      // because the population is unbounded and the label is defined by the
      // hazard itself. The PFAS-formation screen elsewhere on this page is a
      // different thing entirely, and a reader who spots both deserves to be
      // told which is which rather than left to assume a contradiction.
      note: `${facts.gated_domains.join(", ")}. None could carry a withdrawal model; the boundary is the result`,
    },
  ];

  return (
    <section className="border-b border-hairline">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2">
          {built.map((item) => (
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
          under AGPL-3.0. Both benchmark versions, the superseded one and the one that
          replaced it, are published as{" "}
          <a
            href="https://huggingface.co/datasets/MartinBlomqvist/hewb"
            className="text-accent underline underline-offset-2"
          >
            citable datasets
          </a>{" "}
          under CC-BY-4.0.
        </p>
      </div>
    </section>
  );
}
