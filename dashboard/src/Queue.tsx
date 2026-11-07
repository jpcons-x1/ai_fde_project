import { api, type Status } from "./api";
import { DecisionChip, StatusChip } from "./Chip";
import { day, money, sentenceCase } from "./format";
import { useLoad, usePolling } from "./hooks";

const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "awaiting_signoff",
  "decided",
];

export function Queue() {
  const claims = useLoad(api.listClaims);
  const working = claims.data?.some((c) => c.status === "in_progress") ?? false;
  usePolling(working, claims.reload, 2000);

  if (claims.error) return <p className="error">{claims.error}</p>;
  if (!claims.data) return <p className="muted">Loading the queue</p>;
  const all = claims.data;

  return (
    <>
      <section className="tiles" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <div className="panel tile" key={status}>
            <StatusChip status={status} />
            <span className="count" data-testid={`count-${status}`}>
              {all.filter((c) => c.status === status).length}
            </span>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Claims queue</h2>
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Summary</th>
              <th>Submitted</th>
              <th className="amount">Claimed</th>
              <th>Status</th>
              <th>Decision</th>
              <th className="amount">Payout</th>
            </tr>
          </thead>
          <tbody>
            {all.map((claim) => (
              <tr key={claim.claim_id}>
                <td className="nowrap">
                  <a className="mono" href={`#/claims/${claim.claim_id}`}>
                    {claim.claim_id}
                  </a>
                </td>
                <td>{claim.customer_name}</td>
                <td>{sentenceCase(claim.claim_type)}</td>
                <td>{claim.summary}</td>
                <td className="nowrap">{day(claim.submitted_on)}</td>
                <td className="amount">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusChip status={claim.status} />
                </td>
                <td>
                  {claim.decision && <DecisionChip decision={claim.decision} />}
                </td>
                <td className="amount">
                  {claim.payout === null ? "" : money(claim.payout)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
