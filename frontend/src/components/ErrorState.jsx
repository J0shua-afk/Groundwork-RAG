import "./ErrorState.css";

export default function ErrorState({ message, onRetry }) {
  return (
    <section className="error" role="alert">
      <h2 className="error__title">That didn’t work</h2>
      <p>{message}</p>
      <button type="button" className="error__retry" onClick={onRetry}>
        Try again
      </button>
    </section>
  );
}
