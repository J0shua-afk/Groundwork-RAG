import { Fragment } from "react";

import { toBlocks } from "../lib/answerBlocks.js";
import Citation from "./Citation.jsx";
import "./Answer.css";

export default function Answer({ answer, sources, activeSource, onHover, onPick }) {
  const byNumber = new Map(sources.map((source) => [source.number, source]));

  function renderParts(parts) {
    return parts.map((part, index) =>
      part.cite ? (
        <Citation
          key={index}
          number={part.cite}
          source={byNumber.get(part.cite)}
          active={activeSource === part.cite}
          onHover={onHover}
          onPick={onPick}
        />
      ) : (
        <Fragment key={index}>{part.text}</Fragment>
      ),
    );
  }

  return (
    <section className="answer" aria-labelledby="answer-title">
      <h2 id="answer-title" className="visually-hidden">
        Answer
      </h2>
      {toBlocks(answer).map((block, index) =>
        block.type === "list" ? (
          <ul key={index} className="answer__list">
            {block.items.map((parts, item) => (
              <li key={item}>{renderParts(parts)}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>{renderParts(block.parts)}</p>
        ),
      )}
    </section>
  );
}
