import { useState } from "react";
import { api, type Claim } from "./api";
import { DecisionChip } from "./Chip";
import { moment, money } from "./format";
import { useLoad } from "./hooks";

function SignOff({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: () => void }>) {
  const handlers = useLoad(api.listHandlers);
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState("");
  const eligible = (handlers.data ?? []).filter(
    (h) => h.can_approve_over_limit,
  );

  function signOff() {
    api.signOff(claim.claim_id, handlerId).then(onSignedOff, (e: unknown) => {
      setError(String(e));
    });
  }

  return (
    <div className="stack">
      <p className="notice">
        Waiting for sign-off. A payout over {money(claim.payout_approval_limit)}{" "}
        is paid once a handler signs it off.
      </p>
      <div className="sign-off">
        <label htmlFor="handler">Handler</label>
        <select
          id="handler"
          value={handlerId}
          onChange={(e) => {
            setHandlerId(e.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {eligible.map((h) => (
            <option key={h.handler_id} value={h.handler_id}>
              {h.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="button"
          disabled={!handlerId}
          onClick={signOff}
        >
          Sign off and pay
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

export function DecisionPanel({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: () => void }>) {
  const { decision, payment, sign_off: signOff } = claim;

  return (
    <section className="panel stack" aria-label="Decision">
      <h2>Decision</h2>
      {decision ? (
        <>
          <div className="title">
            <DecisionChip decision={decision.decision} />
            <span className="payout">{money(decision.payout)}</span>
          </div>
          <p>{decision.reason}</p>
          <dl className="facts">
            <dt>Policy section</dt>
            <dd>{decision.policy_section}</dd>
            <dt>Decided</dt>
            <dd>{moment(decision.decided_at)}</dd>
            {signOff && (
              <>
                <dt>Signed off by</dt>
                <dd>
                  {signOff.handler_name}, {moment(signOff.signed_at)}
                </dd>
              </>
            )}
            {payment && (
              <>
                <dt>Paid</dt>
                <dd>
                  {money(payment.amount)}, {moment(payment.paid_at)}
                </dd>
              </>
            )}
          </dl>
          {claim.status === "awaiting_signoff" && (
            <SignOff claim={claim} onSignedOff={onSignedOff} />
          )}
        </>
      ) : (
        <p className="muted">No decision yet.</p>
      )}
    </section>
  );
}
