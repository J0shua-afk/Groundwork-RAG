// corpus.js — the words that depend on which postings the API is reading. the live site runs on the
// samples; `npm run dev:private` (vite's --mode private) is for running locally on the real ones

const SAMPLES = {
  title: "Ask about these sample co-op postings",
  note: "A demo running on fictional postings. The real version runs privately on my Winter 2027 co-op search.",
  // all four work on the samples. the last one is unanswerable on purpose, to show the refusal
  examples: [
    "Which roles require Java?",
    "Does the Larkspire role accept undergrads?",
    "What are the term dates for the Quillmoss co-op?",
    "Who is the hiring manager for the Tinderbolt co-op?",
  ],
};

const REAL = {
  title: "Ask about my Winter 2027 co-op postings",
  note: "Running locally on the real postings, which never go to the live site.",
  // no company names, so these still make sense as postings come and go
  examples: [
    "Which roles require Java?",
    "Which roles mention Python?",
    "Which postings ask for a cover letter?",
  ],
};

export const corpus = import.meta.env.MODE === "private" ? REAL : SAMPLES;
