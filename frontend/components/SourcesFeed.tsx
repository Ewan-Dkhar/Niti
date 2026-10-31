"use client";

import { ExternalLink, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { getSources, type SourceItem } from "@/lib/api";

export function SourcesFeed() {
  const [items, setItems] = useState<SourceItem[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getSources(activeQuery, 6)
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setErrors(response.errors);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setItems([]);
        setErrors([error instanceof Error ? error.message : "Live sources are unavailable."]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeQuery]);

  const schemes = items.filter((item) => item.source === "myscheme");
  const releases = items.filter((item) => item.source === "pib");

  return (
    <section id="sources" className="scroll-mt-8 border-t border-rule bg-[#ebe6d8]">
      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="rule-label">Live, not a demo catalogue</p>
            <h2 className="mt-1 font-display text-3xl font-semibold tracking-tight">
              What government is publishing
            </h2>
            <p className="mt-2 max-w-measure text-sm leading-relaxed text-soft">
              Schemes from myScheme and releases from the Press Information Bureau, fetched from
              the source when this page loads.
            </p>
          </div>

          <form
            className="flex w-full max-w-sm items-stretch border border-rule-strong bg-raised focus-within:border-seal"
            onSubmit={(event) => {
              event.preventDefault();
              setActiveQuery(query.trim());
            }}
            role="search"
          >
            <label htmlFor="source-search" className="sr-only">
              Search schemes and releases
            </label>
            <span className="flex items-center pl-3 text-soft" aria-hidden="true">
              <Search size={15} />
            </span>
            <input
              id="source-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-transparent px-2 py-2 text-sm outline-none placeholder:text-[#8a8373]"
              placeholder="farmer, pension, housing"
            />
            <button type="submit" className="border-l border-rule px-3 text-sm font-medium hover:text-seal">
              Search
            </button>
          </form>
        </div>

        {errors.length > 0 ? (
          <div className="mt-5 border border-stamp/30 bg-[#f7e9e4] px-3 py-2 text-xs text-stamp">
            {errors.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </div>
        ) : null}

        <div className="mt-8 grid gap-8 md:grid-cols-2">
          <SourceColumn
            title="Schemes"
            caption="myScheme · Government of India"
            items={schemes}
            loading={loading}
            empty={activeQuery ? "No scheme matched this search." : "No schemes were returned."}
          />
          <SourceColumn
            title="Releases"
            caption="Press Information Bureau"
            items={releases}
            loading={loading}
            empty={
              activeQuery
                ? "No release matched this search."
                : "No releases were returned."
            }
          />
        </div>
      </div>
    </section>
  );
}

function SourceColumn({
  title,
  caption,
  items,
  loading,
  empty,
}: {
  title: string;
  caption: string;
  items: SourceItem[];
  loading: boolean;
  empty: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between border-b border-rule-strong pb-2">
        <h3 className="font-display text-xl font-semibold">{title}</h3>
        <span className="font-mono text-[0.65rem] text-soft">{caption}</span>
      </div>

      {loading ? (
        <div className="mt-4 space-y-4" aria-busy="true" aria-label={`Loading ${title.toLowerCase()}`}>
          {[0, 1, 2].map((row) => (
            <div key={row}>
              <div className="skeleton h-4 w-4/5" />
              <div className="skeleton mt-2 h-3 w-1/3" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="mt-4 text-sm text-soft">{empty}</p>
      ) : (
        <ul className="mt-2">
          {items.map((item) => (
            <li key={item.url} className="border-b border-rule py-3">
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="group flex items-start justify-between gap-3"
              >
                <span>
                  <span className="block text-[0.95rem] font-medium leading-snug group-hover:text-seal">
                    {item.title}
                  </span>
                  {item.summary ? (
                    <span className="mt-1 block text-xs leading-relaxed text-soft">
                      {item.summary}
                    </span>
                  ) : null}
                  {item.published_at ? (
                    <span className="mt-1 block font-mono text-[0.65rem] text-soft">
                      {item.published_at}
                    </span>
                  ) : null}
                </span>
                <ExternalLink
                  size={14}
                  className="mt-1 shrink-0 text-soft group-hover:text-seal"
                  aria-hidden="true"
                />
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
