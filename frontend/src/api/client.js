// client.js — the only module that talks to the backend. components get plain objects back,
// or an ApiError whose message is safe to show as is

export const MAX_QUESTION_CHARS = 500; // the API rejects anything longer

// the backend can spend 30s embedding and 30s generating, so don't give up before it does
const TIMEOUT_MS = 60_000;

export class ApiError extends Error {}

export function getStatus() {
  return request("/api/status");
}

export function ask(question) {
  return request("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    // error bodies aren't always ours: a 422 has pydantic's shape, a rate limit may be HTML
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(body?.error ?? messageFor(response.status));
    }
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") {
      throw new ApiError("That took too long to answer. Try again.");
    }
    throw new ApiError("Couldn't reach Groundwork. Check your connection and try again.");
  } finally {
    clearTimeout(timer);
  }
}

function messageFor(status) {
  if (status === 422) return `Questions can be up to ${MAX_QUESTION_CHARS} characters.`;
  if (status === 429) return "That's a lot of questions in a short time. Wait a minute, then try again.";
  return "Something went wrong on the server. Try again in a moment.";
}
