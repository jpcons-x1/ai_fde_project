import { api } from "./api";
import { useLoad } from "./hooks";

export function Instructions() {
  const instructions = useLoad(api.getInstructions);

  return (
    <section className="panel">
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told before it works a claim. Read only.
      </p>
      {instructions.error && <p className="error">{instructions.error}</p>}
      {instructions.data && (
        <pre className="instructions">{instructions.data.text}</pre>
      )}
    </section>
  );
}
