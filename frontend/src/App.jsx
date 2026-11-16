import Answer from "./components/Answer.jsx";
import EmptyState from "./components/EmptyState.jsx";
import ErrorState from "./components/ErrorState.jsx";
import ExampleQuestions from "./components/ExampleQuestions.jsx";
import Footer from "./components/Footer.jsx";
import Header from "./components/Header.jsx";
import QuestionBox from "./components/QuestionBox.jsx";
import RefusalState from "./components/RefusalState.jsx";
import SourcesPanel from "./components/SourcesPanel.jsx";
import { useGroundwork } from "./state/useGroundwork.js";
import "./App.css";

export default function App() {
  const groundwork = useGroundwork();
  const { asking } = groundwork;

  return (
    <div className="app">
      <Header postings={groundwork.status.postings} />
      <main className="app__main">
        <QuestionBox
          value={groundwork.question}
          onChange={groundwork.setQuestion}
          onSubmit={groundwork.submit}
          asking={asking}
          disabled={groundwork.isEmpty}
        />
        <p className="visually-hidden" role="status">
          {groundwork.announcement}
        </p>
        <div className="app__below">{below(groundwork)}</div>
      </main>
      <Footer />
    </div>
  );
}

// picks what sits under the question box. exactly one of: empty, status error, examples,
// an answer, a refusal or a failed question
function below(groundwork) {
  const { status, result, isEmpty, asking, submit, activeSource } = groundwork;

  if (isEmpty) return <EmptyState />;
  if (!result && status.state === "error") {
    return <ErrorState message={status.error} onRetry={groundwork.retryStatus} />;
  }
  if (!result) return <ExampleQuestions onPick={submit} disabled={asking} />;

  if (result.kind === "answered") {
    return (
      <div className="app__results" key={result.id}>
        <Answer
          answer={result.answer}
          sources={result.sources}
          activeSource={activeSource}
          onHover={groundwork.setHoveredSource}
          onPick={groundwork.setPickedSource}
        />
        <SourcesPanel sources={result.sources} activeSource={activeSource} />
        <ExampleQuestions onPick={submit} disabled={asking} skip={result.question} />
      </div>
    );
  }
  if (result.kind === "refused") {
    return (
      <>
        <RefusalState key={result.id} />
        <ExampleQuestions onPick={submit} disabled={asking} skip={result.question} />
      </>
    );
  }
  if (result.kind === "error") {
    const retry = () => submit(result.question);
    return <ErrorState key={result.id} message={result.message} onRetry={retry} />;
  }
  return <EmptyState />;
}
