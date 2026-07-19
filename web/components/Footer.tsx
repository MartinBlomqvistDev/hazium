export default function Footer() {
  return (
    <footer className="px-6 py-12">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-text-secondary">
          Built by <span className="text-text-primary">Martin Blomqvist</span>.
          Python, XGBoost, SHAP, a hand-rolled temporal graph store. No LangChain.
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
