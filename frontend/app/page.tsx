"use client";

import { AlertCircle, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { CitationDrawer, type CitationTarget } from "@/components/CitationDrawer";
import { DocumentForm } from "@/components/DocumentForm";
import { Footer } from "@/components/Footer";
import { Masthead } from "@/components/Masthead";
import { ResultSheet } from "@/components/ResultSheet";
import { SourcesFeed } from "@/components/SourcesFeed";
import {
  analyzeDocument,
  getResult,
  type AnalysisResult,
  type LanguageCode,
} from "@/lib/api";

type Phase = "idle" | "working" | "done" | "error";

const STEPS = [
  {
    title: "Paste the official PDF",
    copy: "A gazette notification, scheme guideline, or circular hosted on a government site.",
  },
  {
    title: "We read and check it",
    copy: "Rules are pulled out with page and clause citations. Every amount, date, and condition is traced back to the source before it reaches you.",
  },
  {
    title: "Listen, then check your fit",
    copy: "A short spoken briefing in your language, plus a plain eligibility check against the rules we actually read.",
  },
];

export default function HomePage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [documentUrl, setDocumentUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [citation, setCitation] = useState<CitationTarget | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  useEffect(() => {
    if (phase !== "working") return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    if (!result) return;
    const target = document.getElementById("brief");
    if (!target) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }, [result]);

  async function handleAnalyze(url: string, language: LanguageCode) {
    cancelledRef.current = false;
    setPhase("working");
    setElapsed(0);
    setError(null);
    setResult(null);
    setTaskId(null);
    setDocumentUrl(url);
    setCitation(null);

    try {
      const created = await analyzeDocument(url, language);
      if (cancelledRef.current) return;
      setTaskId(created.task_id);

      for (let attempt = 0; attempt < 120; attempt += 1) {
        if (cancelledRef.current) return;
        const response = await getResult(created.task_id);
        if (cancelledRef.current) return;

        if (response.status === "completed" && response.result) {
          setResult(response.result);
          setPhase("done");
          return;
        }
        if (response.status === "failed") {
          throw new Error(response.error ?? "The document could not be processed.");
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }

      throw new Error("This is taking longer than expected. Try a smaller document or check again.");
    } catch (err) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Something went wrong while reading the document.");
      setPhase("error");
    }
  }

  return (
    <>
      <Masthead />

      <main>
        <section className="relative border-b border-rule">
          <div className="mx-auto grid max-w-6xl gap-10 px-5 pb-12 pt-10 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:pb-16 lg:pt-16">
            <div className="flex flex-col justify-center">
              <p className="font-mono text-xs text-soft">स्पष्ट नीति — clear policy</p>
              <h1 className="mt-4 max-w-2xl font-display text-[clamp(2.6rem,6.4vw,4.8rem)] font-bold leading-[0.98] tracking-[-0.035em]">
                The fine print,
                <br />
                in plain speech.
              </h1>
              <p className="mt-5 max-w-measure text-[1.02rem] leading-relaxed text-soft">
                Government documents decide who gets help, how much, and by when. Niti reads the
                original PDF and tells you what it says — in the language you think in, with a
                citation for every claim.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck size={15} className="text-seal" aria-hidden="true" />
                  Checked against the source
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 size={15} className="text-seal" aria-hidden="true" />
                  Five languages
                </span>
              </div>

              <div className="mt-10 grid grid-cols-3 border-y border-rule text-center">
                {["Gazettes", "Schemes", "Circulars"].map((label, index) => (
                  <div
                    key={label}
                    className={`py-3 text-xs font-medium ${
                      index > 0 ? "border-l border-rule" : ""
                    }`}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:pt-4">
              <DocumentForm busy={phase === "working"} onSubmit={handleAnalyze} />

              <div aria-live="polite" className="mt-4">
                {phase === "working" ? (
                  <div className="border border-rule bg-raised px-4 py-4">
                    <p className="flex items-center gap-2 text-sm font-medium">
                      <Loader2 size={15} className="animate-spin text-seal" aria-hidden="true" />
                      Reading the document
                      <span className="font-mono text-xs text-soft">{elapsed}s</span>
                    </p>
                    <div className="progress-track mt-3" role="presentation">
                      <div className="progress-sweep" />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-soft">
                      Fetching the PDF, extracting the rules, and checking each claim against the
                      page it came from.
                    </p>
                  </div>
                ) : null}

                {phase === "error" && error ? (
                  <div className="border border-stamp/40 bg-[#f7e9e4] px-4 py-3">
                    <p className="flex items-start gap-2 text-sm font-medium text-stamp">
                      <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                      {error}
                    </p>
                    <p className="mt-1 pl-6 text-xs leading-relaxed text-soft">
                      Check that the link opens a public PDF, then try again.
                    </p>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="scroll-mt-8 border-b border-rule">
          <div className="mx-auto grid max-w-6xl gap-6 px-5 py-10 sm:px-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <div key={step.title} className="border-t border-rule-strong pt-4">
                <span className="font-mono text-xs text-ochre">0{index + 1}</span>
                <h2 className="mt-1 font-display text-xl font-semibold">{step.title}</h2>
                <p className="mt-1.5 text-sm leading-relaxed text-soft">{step.copy}</p>
              </div>
            ))}
          </div>
        </section>

        {result && taskId ? (
          <ResultSheet result={result} taskId={taskId} onCite={setCitation} />
        ) : null}

        <SourcesFeed />
      </main>

      <Footer />

      <CitationDrawer
        target={citation}
        documentUrl={documentUrl}
        onClose={() => setCitation(null)}
      />
    </>
  );
}
