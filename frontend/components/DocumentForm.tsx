"use client";

import { FileText } from "lucide-react";
import { useState } from "react";

import { LANGUAGES, type LanguageCode } from "@/lib/api";

interface DocumentFormProps {
  busy: boolean;
  onSubmit: (documentUrl: string, language: LanguageCode) => void;
}

export function DocumentForm({ busy, onSubmit }: DocumentFormProps) {
  const [documentUrl, setDocumentUrl] = useState("");
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = documentUrl.trim();
    if (!/^https?:\/\/\S+\.\S+/i.test(value)) {
      setError("Paste the full https:// link to a government PDF.");
      return;
    }
    setError(null);
    onSubmit(value, language);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="relative border border-rule-strong bg-raised p-5 sm:p-6"
      aria-label="Analyze a government document"
    >
      {busy ? (
        <div
          className="seal absolute -right-2 -top-5 animate-stamp-in px-3 py-1.5 text-center font-mono text-[0.65rem] font-medium leading-tight"
          aria-hidden="true"
        >
          READING
          <br />
          THE RECORD
        </div>
      ) : null}

      <p className="rule-label">Document intake</p>
      <h2 className="mt-1 font-display text-2xl font-semibold tracking-tight">
        Give Niti something to read
      </h2>

      <div className="mt-5">
        <label className="field-label" htmlFor="document-url">
          Link to the government PDF
        </label>
        <div className="flex items-stretch border border-rule-strong bg-paper focus-within:border-seal focus-within:ring-1 focus-within:ring-seal">
          <span className="flex items-center border-r border-rule px-3 text-soft" aria-hidden="true">
            <FileText size={16} strokeWidth={1.75} />
          </span>
          <input
            id="document-url"
            name="document-url"
            type="url"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            value={documentUrl}
            onChange={(event) => setDocumentUrl(event.target.value)}
            disabled={busy}
            placeholder="https://labour.gov.in/notification.pdf"
            className="w-full bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-[#8a8373]"
            aria-describedby="document-url-hint"
          />
        </div>
        <p id="document-url-hint" className="mt-2 text-xs leading-relaxed text-soft">
          A public gazette, circular, or scheme PDF. Niti fetches it from the source — you never
          upload a file.
        </p>
      </div>

      <div className="mt-4">
        <label className="field-label" htmlFor="language">
          Read it in
        </label>
        <select
          id="language"
          name="language"
          value={language}
          onChange={(event) => setLanguage(event.target.value as LanguageCode)}
          disabled={busy}
          className="text-field appearance-none"
        >
          {LANGUAGES.map((item) => (
            <option key={item.code} value={item.code}>
              {item.label} — {item.english}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <p className="mt-3 text-sm font-medium text-stamp" role="alert">
          {error}
        </p>
      ) : null}

      <button type="submit" className="button-primary mt-5 w-full" disabled={busy}>
        {busy ? "Reading the document" : "Read this document"}
      </button>

      <p className="mt-3 text-center text-xs text-soft">
        Processing usually takes 20–60 seconds. Long gazettes take longer.
      </p>
    </form>
  );
}
