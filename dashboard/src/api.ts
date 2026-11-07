export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";
export type StepKind = "tool_call" | "tool_result" | "message";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionKind;
  payout: number;
  reason: string;
  policy_section: string;
  decided_at: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  thread_id: string | null;
  agent_running: boolean;
  payout_approval_limit: number;
  decision: Decision | null;
  payment: { amount: number; paid_at: string } | null;
  sign_off: {
    handler_id: string;
    handler_name: string;
    signed_at: string;
  } | null;
}

export interface Policy {
  policy_id: string;
  plan: { plan: string; name: string };
  add_ons: { add_on: string; name: string }[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  number: number;
  thread_id: string;
  kind: StepKind;
  text: string;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(
      `${init?.method ?? "GET"} ${path} failed: ${String(response.status)}`,
    );
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  listClaims: () => request<ClaimSummary[]>("/api/claims"),
  getClaim: (id: string) => request<Claim>(`/api/claims/${id}`),
  getPolicy: (id: string) => request<Policy>(`/api/policies/${id}`),
  getCustomer: (id: string) => request<Customer>(`/api/customers/${id}`),
  listSteps: (id: string) => request<Step[]>(`/api/claims/${id}/steps`),
  getInstructions: () => request<{ text: string }>("/api/instructions"),
  listHandlers: () => request<Handler[]>("/api/handlers"),
  runAgent: (id: string) =>
    post<{ thread_id: string }>(`/api/claims/${id}/run`),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/sign-off`, { handler_id: handlerId }),
};
