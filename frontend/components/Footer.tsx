export function Footer() {
  return (
    <footer className="mt-20 border-t border-rule">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:px-8 md:grid-cols-[1.4fr_1fr]">
        <div>
          <p className="font-display text-xl font-semibold">Niti</p>
          <p className="mt-2 max-w-measure text-sm leading-relaxed text-soft">
            Niti reads public government documents and explains them in plain language. It is not
            legal advice, and an automated reading can miss context. Always confirm the rule and
            the deadline with the ministry, department, or office that issued the document.
          </p>
        </div>
        <div className="text-sm text-soft md:justify-self-end">
          <p className="mb-2 font-medium text-ink">Sources read live</p>
          <ul className="space-y-1">
            <li>
              <a
                className="underline decoration-rule-strong underline-offset-4 hover:text-ink"
                href="https://www.myscheme.gov.in"
                target="_blank"
                rel="noreferrer"
              >
                myScheme, Government of India
              </a>
            </li>
            <li>
              <a
                className="underline decoration-rule-strong underline-offset-4 hover:text-ink"
                href="https://pib.gov.in"
                target="_blank"
                rel="noreferrer"
              >
                Press Information Bureau
              </a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
