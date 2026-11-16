import ExternalLinkIcon from "./ExternalLinkIcon.jsx";
import "./Footer.css";

const REPO_URL = "https://github.com/J0shua-afk/Groundwork-RAG";

export default function Footer() {
  return (
    <footer className="footer">
      <p>
        How it works:{" "}
        <a className="footer__link" href={REPO_URL} target="_blank" rel="noreferrer">
          code and README on GitHub
          <ExternalLinkIcon />
        </a>
      </p>
    </footer>
  );
}
