"use client";

import { AlertTriangle, FileText } from "lucide-react";

import { AudioPlayer } from "@/components/AudioPlayer";
import type { CitationTarget } from "@/components/CitationDrawer";
import { EligibilityPanel } from "@/components/EligibilityPanel";
import { audioUrl, LANGUAGES, type AnalysisResult } from "@/lib/api";

interface ResultSheetProps {
  result: AnalysisResult;
  taskId: string;
  onCite: (target: CitationTarget) => void;
}

const SECTIONS: { key: keyof AnalysisResult["policy_data"]; label: string }[] = [
  { key: "target_beneficiaries", label: "Who it covers" },
  { key: "mandatory_eligibility", label: "To qualify" },
  { key: "direct_benefits", label: "What you get" },
  { key: "required_documents", label: "Documents to bring" },
  { key: "penalty_or_deadlines", label: "Deadlines and penalties" },
  { key: "disqualifications", label: "Who is excluded" },
];

const LANGUAGE_TAGS: Record<string, string> = {
  "hi-IN": "hi",
  "ta-IN": "ta",
  "bn-IN": "bn",
  "te-IN": "te",
  "en-IN": "en",
};

export function ResultSheet({ result, taskId, onCite }: ResultSheetProps) {
  const policy = result.policy_data;
  const audit = result.audit_status;
  const voice = result.voice_payload;
  const script = voice?.plain_text_script ?? "";
  const language =
    LANGUAGES.find((item) => item.code === voice?.language_code) ?? LANGUAGES[4];
  const confidence = Math.round(audit.confidence_score * 100);
  const duration = voice?.duration_estimate_sec ?? 0;

  return (
    <section id="brief" className="scroll-mt-8 border-t border-rule-strong">
      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
        <div className="flex flex-col gap-6 border-b border-rule pb-6 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="rule-label">Policy brief</p>
            <h2 className="mt-1 max-w-3xl font-display text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
              {policy.policy_name}
            </h2>
            <p className="mt-2 text-sm text-soft">{policy.issuing_authority}</p>
            <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-xs">
              {policy.gazette_or_order_no ? (
                <div>
                  <dt className="rule-label">Gazette or order</dt>
                  <dd className="mt-0.5 font-mono text-ink">{policy.gazette_or_order_no}</dd>
                </div>
              ) : null}
              {policy.effective_date ? (
                <div>
                  <dt className="rule-label">Effective date</dt>
                  <dd className="mt-0.5 font-mono text-ink">{policy.effective_date}</dd>
                </div>
              ) : null}
              <div>
                <dt className="rule-label">Read in</dt>
                <dd className="mt-0.5 font-mono text-ink">{language.english}</dd>
              </div>
            </dl>
          </div>

          <div
            className={`seal shrink-0 self-start px-4 py-2 text-center ${
              audit.is_grounded ? "" : "border-stamp"
            }`}
          >
            <span className="block font-mono text-[0.6rem] tracking-[0.08em]">
              GROUNDING CHECK
            </span>
            <span className="mt-0.5 block font-display text-xl font-semibold leading-tight">
              {audit.is_grounded ? "Grounded" : "Needs review"}
            </span>
            <span className="mt-0.5 block font-mono text-[0.65rem]">
              {confidence}% of claims traced
            </span>
          </div>
        </div>

        <div className="mt-8 grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            {result.from_cache ? (
              <p className="mb-4 border-l-2 border-ochre pl-2 text-xs leading-relaxed text-soft">
                The live source could not be reached, so this brief uses the last cached copy of
                the document. Check the original link for any changes since it was saved.
              </p>
            ) : null}
            <p className="rule-label">The spoken briefing</p>
            <div className="mt-2 border-l-2 border-seal pl-4">
              <p
                lang={LANGUAGE_TAGS[language.code]}
                className="whitespace-pre-line text-[1.02rem] leading-[1.85]"
              >
                {script || "No spoken briefing was produced for this document."}
              </p>
            </div>
          </div>

          <aside className="space-y-6 lg:col-span-5">
            <div>
              <p className="rule-label">Listen instead</p>
              <div className="mt-2">
                <AudioPlayer
                  src={audioUrl(result.audio_url)}
                  languageLabel={language.english}
                  durationHint={duration}
                />
              </div>
              <p className="mt-2 text-xs leading-relaxed text-soft">
                Generated from the same extracted facts. The written brief above is the reference
                copy.
              </p>
              {result.audio_is_mock ? (
                <p className="mt-2 border-l-2 border-ochre pl-2 text-xs leading-relaxed text-soft">
                  Demo audio: no Sarvam key is configured, so this file is a placeholder tone
                  rather than a spoken voice.
                </p>
              ) : null}
            </div>

            <EligibilityPanel policyId={taskId} />
          </aside>
        </div>

        {!audit.is_grounded && audit.unsupported_claims.length > 0 ? (
          <div className="mt-10 border border-stamp/40 bg-[#f7e9e4] p-4">
            <p className="flex items-center gap-2 font-medium text-stamp">
              <AlertTriangle size={16} aria-hidden="true" />
              This reading needs a human check
            </p>
            <p className="mt-1 text-sm leading-relaxed text-soft">
              The audit could not find these claims in the source document. Treat them as
              unconfirmed and read the original before relying on them.
            </p>
            <ul className="mt-3 space-y-1 text-sm text-ink">
              {audit.unsupported_claims.map((claim) => (
                <li key={claim} className="border-t border-stamp/20 pt-1 font-mono text-xs">
                  {claim}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-12">
          <div className="flex flex-wrap items-end justify-between gap-2 border-b border-rule-strong pb-2">
            <h3 className="font-display text-2xl font-semibold tracking-tight">The rights sheet</h3>
            <p className="text-xs text-soft">
              Each statement points to the page and clause it came from.
            </p>
          </div>

          <dl>
            {SECTIONS.map(({ key, label }) => {
              const items = policy[key];
              const list = Array.isArray(items) ? (items as string[]) : [];
              return (
                <div
                  key={key}
                  className="grid gap-2 border-b border-rule py-4 md:grid-cols-[12rem_1fr] md:gap-6"
                >
                  <dt className="text-sm font-semibold">{label}</dt>
                  <dd>
                    {list.length === 0 ? (
                      <p className="text-sm text-soft">Not stated in this document.</p>
                    ) : (
                      <ul className="space-y-3">
                        {list.map((item, index) => {
                          const citation = policy.citation_source_map[`${key}[${index}]`];
                          return (
                            <li key={`${key}-${index}`} className="flex gap-2.5 text-[0.95rem]">
                              <span
                                className="mt-2 h-1.5 w-1.5 shrink-0 bg-ochre"
                                aria-hidden="true"
                              />
                              <div className="min-w-0">
                                <p className="leading-relaxed">{item}</p>
                                {citation ? (
                                  <button
                                    type="button"
                                    className="button-quiet mt-1.5"
                                    onClick={() => onCite({ field: label, text: item, citation })}
                                  >
                                    <FileText size={12} aria-hidden="true" />
                                    {citation}
                                  </button>
                                ) : (
                                  <p className="mt-1 font-mono text-[0.68rem] text-soft">
                                    No citation recorded
                                  </p>
                                )}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-soft">
          Niti reads public documents; it is not a lawyer or a deciding officer. Rules can change
          after the date this document was published. Confirm the current position with{" "}
          <span className="text-ink">{policy.issuing_authority}</span>.
        </p>
      </div>
    </section>
  );
}
