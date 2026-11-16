// useGroundwork.js — everything the screen knows: the postings count, the question, the latest
// result, and which citation is lit up. components read this; only the api client fetches

import { useCallback, useEffect, useRef, useState } from "react";

import { ask, getStatus } from "../api/client.js";

export function useGroundwork() {
  const [status, setStatus] = useState({ state: "loading", postings: null, error: null });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  // { id, kind: "answered" | "refused" | "empty" | "error", question, answer, sources, message }
  const [result, setResult] = useState(null);
  // hover lights a source while the pointer is there; a click keeps one lit until the next
  // question. hover wins so you can still compare against the picked one
  const [hoveredSource, setHoveredSource] = useState(null);
  const [pickedSource, setPickedSource] = useState(null);
  const nextId = useRef(1);

  const fetchStatus = useCallback(
    () =>
      getStatus().then(
        ({ postings }) => setStatus({ state: "ready", postings, error: null }),
        (error) => setStatus({ state: "error", postings: null, error: error.message }),
      ),
    [],
  );

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const retryStatus = useCallback(() => {
    setStatus({ state: "loading", postings: null, error: null });
    fetchStatus();
  }, [fetchStatus]);

  const submit = useCallback(async (text) => {
    const asked = text.trim();
    if (!asked) return;
    setQuestion(asked);
    setAsking(true);
    setHoveredSource(null);
    setPickedSource(null);
    // the id changes on every result, so the answer's entrance plays again
    const id = nextId.current++;
    try {
      const body = await ask(asked);
      const { outcome, answer, sources } = body;
      setResult({ id, kind: outcome, question: asked, answer, sources });
      if (outcome === "empty") setStatus({ state: "ready", postings: 0, error: null });
    } catch (error) {
      setResult({ id, kind: "error", question: asked, message: error.message });
    } finally {
      setAsking(false);
    }
  }, []);

  const isEmpty = status.state === "ready" && status.postings === 0;

  return {
    status,
    question,
    setQuestion,
    asking,
    result,
    activeSource: hoveredSource ?? pickedSource,
    setHoveredSource,
    setPickedSource,
    submit,
    retryStatus,
    isEmpty,
    announcement: announce(asking, result),
  };
}

// a short line for screen readers. announcing the whole results area would read every snippet
// out loud. errors aren't here because ErrorState is already an alert
function announce(asking, result) {
  if (asking) return "Looking through the postings…";
  if (result?.kind === "answered") {
    const count = result.sources.length;
    return `Answer ready, with ${count} ${count === 1 ? "source" : "sources"}.`;
  }
  if (result?.kind === "refused") return "That isn’t in the postings.";
  if (result?.kind === "empty") return "No postings are loaded yet.";
  return "";
}
