import Link from "next/link";

/**
 * Four destinations, which is the most that fits beside the wordmark on a
 * 360px phone. "Method" hides below 400px, since a reader on the narrowest
 * screens is the least likely to want the feature-group table.
 */
export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-page/85 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
          Hazium
        </Link>
        <nav className="flex items-center gap-3 text-sm text-text-secondary sm:gap-6">
          <Link href="/method" className="hidden py-1.5 hover:text-text-primary min-[400px]:inline">
            Method
          </Link>
          <Link href="/watchlist" className="py-1.5 hover:text-text-primary">
            Watchlist
          </Link>
          <Link href="/explorer" prefetch={false} className="py-1.5 hover:text-text-primary">
            Explorer
          </Link>
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
