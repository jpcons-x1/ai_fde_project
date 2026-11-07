import { useCallback, useEffect, useState } from "react";
import { api, type Claim } from "./api";
import { Activity } from "./Activity";
import { StatusChip } from "./Chip";
import { DecisionPanel } from "./DecisionPanel";
import { day, money, sentenceCase } from "./format";
import { useLoad, usePolling } from "./hooks";

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-label="Claim">
      <h2>The claim</h2>
      <dl className="facts">
        <dt>Type</dt>
        <dd>{sentenceCase(claim.claim_type)}</dd>
        <dt>Incident</dt>
        <dd>
          {day(claim.incident_date)}, {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd>{day(claim.submitted_on)}</dd>
      </dl>
      <h3 className="spaced">The customer's story</h3>
      <p>{claim.story}</p>
      <h3>Items claimed</h3>
      <table>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{sentenceCase(item.category)}</td>
              <td className="amount">{money(item.amount)}</td>
            </tr>
          ))}
          <tr>
            <td>
              <strong>Total claimed</strong>
            </td>
            <td />
            <td className="amount">
              <strong>{money(claim.amount_claimed)}</strong>
            </td>
          </tr>
        </tbody>
      </table>
      <h3 className="spaced">Documents</h3>
      {claim.documents.map((document) => (
        <div className="document" key={document.name}>
          <strong>{document.name}</strong>
          <p>{document.content}</p>
        </div>
      ))}
    </section>
  );
}

function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const load = useCallback(() => api.getPolicy(policyId), [policyId]);
  const policy = useLoad(load).data;
  if (!policy) return null;

  return (
    <section className="panel" aria-label="Policy">
      <h2>Policy</h2>
      <dl className="facts">
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan.name}</dd>
        <dt>Add-ons</dt>
        <dd>{policy.add_ons.map((a) => a.name).join(", ") || "None"}</dd>
        <dt>Bought</dt>
        <dd>{day(policy.purchased_on)}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {day(policy.trip.departs_on)} to{" "}
          {day(policy.trip.returns_on)}
        </dd>
        <dt>Trip cost</dt>
        <dd>{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
      </dl>
    </section>
  );
}

function CustomerPanel({ customerId }: Readonly<{ customerId: string }>) {
  const load = useCallback(() => api.getCustomer(customerId), [customerId]);
  const customer = useLoad(load).data;
  if (!customer) return null;

  return (
    <section className="panel" aria-label="Customer">
      <h2>{customer.name}</h2>
      <p className="muted">Customer since {day(customer.customer_since)}</p>
      <h3>Earlier claims</h3>
      {customer.previous_claims.length === 0 && <p className="muted">None.</p>}
      {customer.previous_claims.map((c) => (
        <div className="document" key={c.claim_id}>
          <span className="mono">{c.claim_id}</span>, {day(c.filed_on)}
          <p>
            {c.summary}. {sentenceCase(c.outcome)}, {money(c.amount_paid)} paid.
          </p>
        </div>
      ))}
    </section>
  );
}

function RunButton({
  claimId,
  onStarted,
}: Readonly<{ claimId: string; onStarted: () => void }>) {
  const [error, setError] = useState("");

  function start() {
    api.runAgent(claimId).then(onStarted, (e: unknown) => {
      setError(String(e));
    });
  }

  return (
    <>
      <button type="button" className="button" onClick={start}>
        Run the agent
      </button>
      {error && <p className="error">{error}</p>}
    </>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const loadClaim = useCallback(() => api.getClaim(claimId), [claimId]);
  const loadSteps = useCallback(() => api.listSteps(claimId), [claimId]);
  const claim = useLoad(loadClaim);
  const steps = useLoad(loadSteps);
  const { reload: reloadClaim } = claim;
  const { reload: reloadSteps } = steps;
  const running = claim.data?.agent_running ?? false;

  const refresh = useCallback(() => {
    reloadClaim();
    reloadSteps();
  }, [reloadClaim, reloadSteps]);
  usePolling(running, refresh, 2000);

  // Fetch the last steps once a run ends, as the final poll can miss them.
  useEffect(reloadSteps, [running, reloadSteps]);

  if (claim.error) return <p className="error">{claim.error}</p>;
  if (!claim.data) return <p className="muted">Loading the claim</p>;
  const data = claim.data;

  return (
    <>
      <section className="panel title">
        <h1 className="mono">{data.claim_id}</h1>
        <StatusChip status={data.status} />
        <span>{data.summary}</span>
        {data.status === "waiting" && !running && (
          <RunButton claimId={data.claim_id} onStarted={refresh} />
        )}
      </section>
      <div className="columns">
        <div className="stack">
          <DecisionPanel claim={data} onSignedOff={refresh} />
          <Activity steps={steps.data ?? []} running={running} />
          <ClaimDetails claim={data} />
        </div>
        <div className="stack">
          <PolicyPanel policyId={data.policy_id} />
          <CustomerPanel customerId={data.customer_id} />
        </div>
      </div>
    </>
  );
}
