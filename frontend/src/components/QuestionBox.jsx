import { useRef } from "react";

import { MAX_QUESTION_CHARS } from "../api/client.js";
import "./QuestionBox.css";

const SHOW_COUNT_FROM = 400; // the counter only earns its space near the limit

export default function QuestionBox({ value, onChange, onSubmit, asking, disabled }) {
  const input = useRef(null);

  function submit(event) {
    event.preventDefault();
    if (asking || disabled) return;
    // an empty Ask puts you back in the box rather than doing nothing
    if (!value.trim()) {
      input.current.focus();
      return;
    }
    onSubmit(value);
  }

  function handleKeyDown(event) {
    // Enter asks, Shift+Enter is a new line; isComposing keeps IME input working
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      submit(event);
    }
  }

  return (
    <form className="question" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="question-input">
        Your question about the postings
      </label>
      <div className="question__field">
        <textarea
          ref={input}
          id="question-input"
          className="question__input"
          rows={2}
          dir="auto"
          maxLength={MAX_QUESTION_CHARS}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          // no example to copy when there's nothing to ask about
          placeholder={disabled ? "" : "Which roles require Java?"}
          disabled={disabled}
        />
        <div className="question__bar">
          {value.length >= SHOW_COUNT_FROM && (
            <span className="question__count">
              {value.length}/{MAX_QUESTION_CHARS}
            </span>
          )}
          <button type="submit" className="question__ask" disabled={disabled} aria-busy={asking}>
            {asking && <span className="question__spinner" aria-hidden="true" />}
            {asking ? "Asking" : "Ask"}
          </button>
        </div>
      </div>
    </form>
  );
}
