---
name: pexip-external-policy
description: Use when building or extending Pexip's External Policy Server integration — a custom HTTP service Pexip Infinity consults at call setup to make routing, authentication, or admission decisions that go beyond the built-in dial plan. Triggers on `external_policy_server`, `/api/admin/configuration/v1/external_policy_server/`, `policy_request`, `service_lookup`, `participant_avatar_lookup`, `participant_properties_lookup`, "external policy", "policy server", "custom call routing", "per-call decisions", "dynamic VMR". Do NOT use for static dial-plan rules (use `pexip-config-api` / `pexip-operations/dial-plan.md`) or for runtime command/control (use `pexip-command-api`).
license: MIT
---

# Pexip external policy server

The **External Policy API** lets Pexip Infinity outsource per-call decisions to an HTTP service you run. At well-defined hook points (call setup, service lookup, avatar lookup, participant property lookup), Pexip POSTs a request to your endpoint and applies the JSON response — overriding or augmenting the static dial plan.

Use it when the answer to "where should this call go?" depends on data Pexip doesn't have: your CRM, scheduling system, real-time capacity heuristics, custom auth, dynamic VMRs per booking, etc.

> **Status: stub.** This skill is a placeholder for the next round of coverage. The Pexip External Policy API is real and supported, but the `pexip-mgmt-mcp` server does **not** currently wrap the `external_policy_server` resource. Adding it is on the roadmap (see `CHANGELOG.md` / parent repo's `TODO.md`).

## When to use

- "Build a dynamic VMR per calendar invite" (booking system → VMR creation on demand)
- "Authenticate calls against our SSO before allowing join"
- "Route calls to the lowest-loaded location at the moment of dial"
- "Inject custom branding / display names per call"
- Adding `external_policy_server` CRUD tools to the MCP server

## When NOT to use

- Static dial plan with regex matching → `pexip-config-api` (`gateway_routing_rule`) / `pexip-operations/dial-plan.md`
- Persistent VMRs configured ahead of time → `pexip-operations/vmr-administration.md`
- Runtime kick/lock/mute → `pexip-command-api`

## Hook points (high-level)

The Pexip External Policy API defines several request types. Pexip POSTs JSON to your endpoint with the request type and call context; you return JSON describing the decision.

| Hook | When fired | Typical use |
|---|---|---|
| `service_lookup` | A call arrives and Pexip needs to find/create the service it joins | Dynamic VMR creation, per-booking conferences |
| `participant_lookup` | Participant identity needs verification | SSO / external auth integration |
| `participant_avatar_lookup` | Need an avatar URL for a participant | Pull from your directory |
| `participant_properties_lookup` | Need custom properties (display name overrides, role, location) | Per-call branding |

Exact request/response schemas vary across Pexip Infinity versions — **read the authoritative doc** before implementing. Pexip ships canned examples for each hook.

## Receiver-side contract

Same general shape as event sinks but synchronous:

1. **Accept POST**, return **200** with a JSON body shaped per Pexip's spec.
2. **Be fast.** Pexip blocks the call setup waiting for your response — multi-second latency is a user-visible "slow to connect" issue.
3. **Be deterministic** for testability. Pexip retries on 5xx but not on 4xx; idempotency-by-input is the easiest contract.
4. **TLS auth.** Pexip can present a client cert; configure mutual TLS if you need to verify the request really came from your Management Node.

## Configuration (when MCP coverage lands)

Future tools (not yet implemented in the server):

```
list_external_policy_servers(…)
create_external_policy_server(name=…, url=…, ssl_cert=…, …)
update_external_policy_server(…)
delete_external_policy_server(…)
```

Until then: configure via Pexip's admin UI under **Call Control → External Policy** and consult the doc.

## Field gotchas (anticipated, verify when implementing)

- Policy server responses can include URIs to dynamically created configuration objects — make sure your creator side responds with valid URIs Pexip can parse.
- The policy server is in the synchronous path of call setup; outages cause join failures. Always have a fallback (e.g. fall through to static dial plan).
- Pexip versions before v30 had some response-schema deltas around service properties; if you support older deployments, branch on version.

## Reference source

- **Authoritative Pexip docs:**
  - External policy overview: https://docs.pexip.com/admin/external_policy.htm
  - API reference: https://docs.pexip.com/api_manage/api_external_policy.htm
- **Reference implementation (MCP):** _not yet implemented_ — could be added to [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp) as `src/pexip_mcp/tools/external_policy.py` per the existing pattern. Until then, call the REST endpoints directly.
- **Related skills:** `pexip-config-api` (existing resource model), `pexip-operations/dial-plan.md` (the static-rule alternative), `pexip-event-sinks` (the push-event sibling)
