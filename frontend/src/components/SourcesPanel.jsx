import ExternalLinkIcon from "./ExternalLinkIcon.jsx";
import "./SourcesPanel.css";

export default function SourcesPanel({ sources, activeSource }) {
  // each chunk is its own source, so one posting can show up twice. the repeat only needs
  // its snippet; the details are already on the first one
  const firstNumber = new Map();
  for (const source of sources) {
    if (!firstNumber.has(source.source_id)) firstNumber.set(source.source_id, source.number);
  }

  return (
    <section className="sources" aria-labelledby="sources-title">
      <h2 id="sources-title" className="sources__title">
        Sources
      </h2>
      <ol className="sources__list">
        {sources.map((source) => {
          const first = firstNumber.get(source.source_id);
          const isRepeat = first !== source.number;
          return (
            <li
              key={source.number}
              id={`source-${source.number}`}
              className={activeSource === source.number ? "source source--active" : "source"}
            >
              <span className="source__number">[{source.number}]</span>
              <div className="source__body">
                <h3 className="source__company">{source.company}</h3>
                <p className="source__title">{source.title}</p>
                {isRepeat ? (
                  <p className="source__meta">
                    Same posting as <span className="source__ref">[{first}]</span>
                  </p>
                ) : (
                  <>
                    {/* mono is for real dates only, not for the "not stated" fallback */}
                    <p className={isStated(source.term) ? "source__term" : "source__meta"}>
                      {stated(source.term, "Term")}
                    </p>
                    <p className="source__meta">
                      {stated(source.location, "Location")} ·{" "}
                      {stated(source.work_model, "Work model")}
                    </p>
                  </>
                )}
                <p className="source__snippet">{source.snippet}</p>
                {/* the source id is the posting's file name minus .txt; the full name reads as
                    "the file this came from" instead of an internal id */}
                {!isRepeat && <p className="source__id">{source.source_id}.txt</p>}
                {!isRepeat && source.url && (
                  <a className="source__link" href={source.url} target="_blank" rel="noreferrer">
                    View posting
                    <ExternalLinkIcon />
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// the posting header uses "not stated" for anything the posting leaves out
function isStated(value) {
  return value.trim().toLowerCase() !== "not stated";
}

function stated(value, label) {
  return isStated(value) ? value : `${label} not stated`;
}
