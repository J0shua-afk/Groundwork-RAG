import { corpus } from "../corpus.js";
import "./ExampleQuestions.css";

// skip: the question just asked, so it isn't offered straight back
export default function ExampleQuestions({ onPick, disabled, skip }) {
  return (
    <section className="examples" aria-labelledby="examples-title">
      <h2 id="examples-title" className="examples__title">
        Try one of these
      </h2>
      <ul className="examples__list">
        {corpus.examples
          .filter((example) => example !== skip)
          .map((example) => (
            <li key={example}>
              <button
                type="button"
                className="examples__button"
                onClick={() => onPick(example)}
                disabled={disabled}
              >
                {example}
              </button>
            </li>
          ))}
      </ul>
    </section>
  );
}
