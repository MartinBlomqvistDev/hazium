export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-page/85 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <a href="#top" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
          Hazium
        </a>
        <nav className="flex items-center gap-6 text-sm text-text-secondary">
          <a href="#result" className="hover:text-text-primary">
            The result
          </a>
          <a href="#how" className="hover:text-text-primary">
            How it works
          </a>
          <a href="#principles" className="hover:text-text-primary">
            Principles
          </a>
          <a
            href="https://github.com/MartinBlomqvistDev/hazium"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-hairline px-3 py-1.5 text-text-primary hover:border-accent hover:text-accent"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
