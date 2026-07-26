import Link from "next/link";

export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-page/85 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/#top" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
          Hazium
        </Link>
        <nav className="flex items-center gap-3 text-sm text-text-secondary sm:gap-6">
          {/* Hidden below 400px: the four items plus the wordmark overflow a 360px
              phone by a few pixels, which puts the whole page into sideways scroll. */}
          <Link href="/#how" className="hidden hover:text-text-primary min-[400px]:inline">
            How it works
          </Link>
          <Link href="/#anchor" className="hover:text-text-primary">
            What it misses
          </Link>
          <Link href="/explorer" className="hover:text-text-primary">
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
