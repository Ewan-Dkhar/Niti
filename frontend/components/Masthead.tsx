import Link from "next/link";

export function Masthead() {
  return (
    <header className="border-b border-rule bg-paper">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="Niti home">
          <span className="font-display text-[1.9rem] font-bold leading-none tracking-tight">
            Niti
          </span>
          <span className="border border-rule-strong px-1.5 py-1 font-mono text-[0.68rem] leading-none text-soft">
            नीति
          </span>
          <span className="hidden text-sm text-soft sm:inline">Policy, in plain words.</span>
        </Link>

        <nav className="flex items-center gap-5 text-sm" aria-label="Primary">
          <a href="#how" className="text-soft hover:text-ink">
            How it works
          </a>
          <a href="#sources" className="text-soft hover:text-ink">
            Live sources
          </a>
        </nav>
      </div>
    </header>
  );
}
