import "./EmptyState.css";

export default function EmptyState() {
  return (
    <section className="empty" aria-labelledby="empty-title">
      <h2 id="empty-title" className="empty__title">
        No postings are loaded yet
      </h2>
      <p>
        Groundwork answers only from job postings, and none have been added to this site yet. Once
        they are, you can ask about them here, and every answer will point to the posting it came
        from.
      </p>
    </section>
  );
}
