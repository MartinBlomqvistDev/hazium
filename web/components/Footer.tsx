export default function Footer() {
  return (
    <footer className="px-6 py-12">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-text-secondary">
          Built by{" "}
          <span className="text-text-primary">Martin Blomqvist</span> — Python,
          XGBoost, SHAP, a hand-rolled temporal graph store. No LangChain.
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary">
          <a
            href="https://github.com/MartinBlomqvistDev/hazium"
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            Hazium on GitHub
          </a>
          <span className="text-hairline">·</span>
          <a
            href="https://prasineindex.com"
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            Prasine Index
          </a>
          <span className="text-hairline">·</span>
          <a
            href="https://web-seven-tau-89.vercel.app"
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            MaktspråkAI
          </a>
        </div>
      </div>
    </footer>
  );
}
