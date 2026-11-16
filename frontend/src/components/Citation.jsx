import "./Citation.css";

export default function Citation({ number, source, active, onHover, onPick }) {
  // the backend only keeps citations to real sources, so this is just a safety net
  if (!source) return `[${number}]`;

  function pick(event) {
    // no hash jump: that would throw the answer off screen on a wide layout, where the source
    // is usually already visible. "nearest" only scrolls if it isn't
    event.preventDefault();
    onPick(number);
    document.getElementById(`source-${number}`)?.scrollIntoView({ block: "nearest" });
  }

  return (
    <a
      href={`#source-${number}`}
      className={active ? "citation citation--active" : "citation"}
      aria-label={`Source ${number}: ${source.company}, ${source.title}`}
      onClick={pick}
      onMouseEnter={() => onHover(number)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(number)}
      onBlur={() => onHover(null)}
    >
      [{number}]
    </a>
  );
}
