import type { DecisionKind, Status } from "./api";
import { DECISION_LABELS, STATUS_LABELS } from "./format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status]}</span>;
}

export function DecisionChip({
  decision,
}: Readonly<{ decision: DecisionKind }>) {
  return (
    <span className={`chip chip-${decision}`}>{DECISION_LABELS[decision]}</span>
  );
}
