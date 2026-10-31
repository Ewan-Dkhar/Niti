import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        raised: "var(--paper-raised)",
        ink: "var(--ink)",
        soft: "var(--ink-soft)",
        rule: "var(--rule)",
        "rule-strong": "var(--rule-strong)",
        seal: "var(--seal)",
        "seal-deep": "var(--seal-deep)",
        stamp: "var(--stamp)",
        ochre: "var(--ochre)",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: [
          "var(--font-body)",
          "var(--font-devanagari)",
          "var(--font-tamil)",
          "var(--font-bengali)",
          "var(--font-telugu)",
          "system-ui",
          "sans-serif",
        ],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      maxWidth: {
        measure: "68ch",
      },
      keyframes: {
        "stamp-in": {
          "0%": { opacity: "0", transform: "rotate(-3deg) scale(1.12)" },
          "70%": { opacity: "1", transform: "rotate(-3deg) scale(0.98)" },
          "100%": { opacity: "1", transform: "rotate(-3deg) scale(1)" },
        },
      },
      animation: {
        "stamp-in": "stamp-in 420ms cubic-bezier(0.2, 0.9, 0.3, 1.2) both",
      },
    },
  },
  plugins: [],
};
export default config;
