import type { Step } from "./api";

const KIND_LABELS: Record<Step["kind"], string> = {
  tool_call: "Tool call",
  tool_result: "Result",
  message: "Agent",
};

export function Activity({
  steps,
  running,
}: Readonly<{ steps: Step[]; running: boolean }>) {
  return (
    <section className="panel" aria-label="Agent activity">
      <h2>Agent activity</h2>
      {running && <p className="muted">The agent is working on this claim.</p>}
      {steps.length === 0 && !running && (
        <p className="muted">The agent hasn't worked on this claim yet.</p>
      )}
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.number} className={`step step-${step.kind}`}>
            <span className="step-number">{step.number}</span>
            <div>
              <span className="step-kind">{KIND_LABELS[step.kind]}</span>
              <pre>{step.text}</pre>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
