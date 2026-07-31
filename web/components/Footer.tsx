import buildFactsData from "@/data/build.json";
import type { BuildFacts } from "@/lib/types";

const facts = buildFactsData as BuildFacts;

/**
 * The five sources live here rather than in the landing page's link list, where
 * they hung off the "Code on GitHub" row. They are a fact about the project,
 * not about the repository, so nobody wondering what data this is built on
 * would have looked for them under a link to the code.
 */
export default function Footer() {
  const sources = facts.model_sources;
  const named = `${sources.slice(0, -1).join(", ")} and ${sources[sources.length - 1]}`;

  return (
    <footer className="px-6 py-12">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl text-sm text-text-secondary">
          Built by <span className="text-text-primary">Martin Blomqvist</span>. Python,
          XGBoost, SHAP, and a knowledge graph over {named}, every fact carrying the date
          it became public.
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary">
          <a
            href="https://github.com/MartinBlomqvistDev/hazium"
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            GitHub
          </a>
          <span className="text-hairline">·</span>
          <a
            href="https://www.linkedin.com/in/martin-blomqvist"
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            LinkedIn
          </a>
          <span className="text-hairline">·</span>
          <a href="mailto:cm.blomqvist@gmail.com" className="hover:text-accent">
            Email
          </a>
        </div>
      </div>
    </footer>
  );
}
