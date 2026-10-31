"use client";

import { ExternalLink, X } from "lucide-react";
import { useEffect, useRef } from "react";

export interface CitationTarget {
  field: string;
  text: string;
  citation: string;
}

interface CitationDrawerProps {
  target: CitationTarget | null;
  documentUrl: string;
  onClose: () => void;
}

export function CitationDrawer({ target, documentUrl, onClose }: CitationDrawerProps) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!target) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;

      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [target, onClose]);

  if (!target) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-ink/40"
        aria-label="Close the source note"
        onClick={onClose}
        tabIndex={-1}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-title"
        className="relative flex h-full w-full max-w-md flex-col border-l border-rule-strong bg-raised shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-rule px-5 py-4">
          <div>
            <p className="rule-label">Source note</p>
            <h3 id="citation-title" className="mt-1 font-display text-xl font-semibold">
              {target.field}
            </h3>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="border border-rule-strong p-1.5 text-soft hover:border-seal hover:text-seal"
            aria-label="Close the source note"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-6">
          <p className="text-[0.95rem] leading-relaxed">{target.text}</p>

          <div className="mt-6 border-t border-rule pt-4">
            <p className="rule-label">Where this comes from</p>
            <p className="mt-1 font-mono text-sm text-seal">{target.citation}</p>
            <p className="mt-3 text-xs leading-relaxed text-soft">
              This is the statement Niti extracted and the page and clause the grounding check
              matched it against. Read the original document before acting on it.
            </p>
            <a
              href={documentUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-seal underline decoration-rule-strong underline-offset-4 hover:text-seal-deep"
            >
              Open the source document
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </div>
        </div>
      </aside>
    </div>
  );
}
