"use client";

import { AlertCircle, Check, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { verifyCitizen, type VerifyResponse } from "@/lib/api";

const STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Delhi",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Puducherry",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
];

interface EligibilityPanelProps {
  policyId: string;
}

export function EligibilityPanel({ policyId }: EligibilityPanelProps) {
  const [income, setIncome] = useState("");
  const [occupation, setOccupation] = useState("");
  const [state, setState] = useState("");
  const [documents, setDocuments] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<VerifyResponse | null>(null);

  useEffect(() => {
    setVerdict(null);
    setError(null);
  }, [policyId]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedIncome = Number(income);
    if (!income.trim() || !Number.isFinite(parsedIncome) || parsedIncome < 0) {
      setError("Enter your annual household income in rupees.");
      return;
    }
    if (!occupation.trim() || !state.trim()) {
      setError("Add your occupation and state so the rules can be checked.");
      return;
    }

    setError(null);
    setPending(true);
    setVerdict(null);
    try {
      const response = await verifyCitizen(policyId, {
        income: Math.round(parsedIncome),
        occupation: occupation.trim(),
        state: state.trim(),
        documents: documents
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setVerdict(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check eligibility.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="eligibility-title" className="border border-rule bg-raised">
      <div className="border-b border-rule px-5 py-4">
        <p className="rule-label">Your situation</p>
        <h3 id="eligibility-title" className="mt-1 font-display text-xl font-semibold">
          Do these rules cover you?
        </h3>
        <p className="mt-1 text-sm leading-relaxed text-soft">
          Niti compares your answers with the rules it read. It does not decide your application.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 px-5 py-5">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="field-label" htmlFor="income">
              Annual income (₹)
            </label>
            <input
              id="income"
              type="number"
              min="0"
              step="1000"
              value={income}
              onChange={(event) => setIncome(event.target.value)}
              className="text-field"
              placeholder="180000"
            />
          </div>
          <div>
            <label className="field-label" htmlFor="state">
              State or UT
            </label>
            <input
              id="state"
              list="state-options"
              value={state}
              onChange={(event) => setState(event.target.value)}
              className="text-field"
              placeholder="Delhi"
            />
            <datalist id="state-options">
              {STATES.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>
        </div>

        <div>
          <label className="field-label" htmlFor="occupation">
            What do you do?
          </label>
          <input
            id="occupation"
            value={occupation}
            onChange={(event) => setOccupation(event.target.value)}
            className="text-field"
            placeholder="street vendor, farmer, salaried employee"
          />
        </div>

        <div>
          <label className="field-label" htmlFor="documents">
            Documents you already have
          </label>
          <input
            id="documents"
            value={documents}
            onChange={(event) => setDocuments(event.target.value)}
            className="text-field"
            placeholder="Aadhaar Card, Ration Card, bank passbook"
          />
          <p className="mt-1 text-xs text-soft">Separate each document with a comma.</p>
        </div>

        {error ? (
          <p className="flex items-start gap-2 text-sm font-medium text-stamp" role="alert">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {error}
          </p>
        ) : null}

        <button type="submit" className="button-primary w-full" disabled={pending}>
          {pending ? (
            <>
              <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              Checking the rules
            </>
          ) : (
            "Check my eligibility"
          )}
        </button>
      </form>

      {verdict ? (
        <div className="border-t border-rule px-5 py-5" aria-live="polite">
          <div
            className={`inline-flex animate-stamp-in flex-col border-2 px-3 py-1.5 ${
              verdict.is_eligible ? "border-seal text-seal" : "border-stamp text-stamp"
            }`}
          >
            <span className="font-mono text-[0.6rem] tracking-[0.08em]">
              {verdict.is_eligible ? "NO BLOCKING CLAUSE" : "A RULE EXCLUDES YOU"}
            </span>
            <span className="flex items-center gap-1.5 font-display text-lg font-semibold leading-tight">
              {verdict.is_eligible ? (
                <Check size={17} aria-hidden="true" />
              ) : (
                <X size={17} aria-hidden="true" />
              )}
              {verdict.is_eligible ? "Likely eligible" : "Not eligible"}
            </span>
          </div>

          {verdict.matched_clauses.length > 0 ? (
            <div className="mt-4">
              <p className="rule-label">Clauses that matched</p>
              <ul className="mt-2 space-y-2">
                {verdict.matched_clauses.map((clause) => (
                  <li key={clause} className="flex gap-2 text-sm leading-relaxed">
                    <span
                      className="mt-2 h-1.5 w-1.5 shrink-0 bg-ochre"
                      aria-hidden="true"
                    />
                    <span>{clause}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-relaxed text-soft">
              No specific clause in this document blocked you. Confirm the details with the
              issuing office before you apply.
            </p>
          )}

          {verdict.missing_documents.length > 0 ? (
            <div className="mt-4 border-t border-rule pt-4">
              <p className="rule-label">Bring these documents</p>
              <ul className="mt-2 space-y-1 text-sm">
                {verdict.missing_documents.map((document) => (
                  <li key={document} className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 bg-stamp" aria-hidden="true" />
                    <span>{document}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
