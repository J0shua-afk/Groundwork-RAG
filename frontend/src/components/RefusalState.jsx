import "./RefusalState.css";

export default function RefusalState() {
  return (
    <section className="refusal" aria-labelledby="refusal-title">
      <h2 id="refusal-title" className="refusal__title">
        That isn’t in the postings
      </h2>
      <p>
        Groundwork answers only from what it finds in the postings, and it didn’t find this.
        Asking in different words can help.
      </p>
    </section>
  );
}
