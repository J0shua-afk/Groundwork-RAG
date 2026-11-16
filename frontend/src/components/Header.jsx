import { corpus } from "../corpus.js";
import "./Header.css";

export default function Header({ postings }) {
  return (
    <header className="header">
      <h1 className="header__title">{keepCoopTogether(corpus.title)}</h1>
      <p className="header__note">{keepCoopTogether(corpus.note)}</p>
      {/* only a real count shows here; loading and errors are handled below the question */}
      {postings != null && (
        <p className="header__count">
          {postings} {postings === 1 ? "posting" : "postings"} loaded
        </p>
      )}
    </header>
  );
}

// Barlow has no non-breaking hyphen, so without this "co-op" can split across two lines
function keepCoopTogether(text) {
  return text.split(/(co-op)/).map((part, index) =>
    part === "co-op" ? (
      <span key={index} className="no-break">
        co-op
      </span>
    ) : (
      part
    ),
  );
}
