---
name: pexip-external-policy
description: Build and extend Pexip's External Policy Server integration — a custom HTTP service Pexip Infinity consults at call setup to make routing, authentication, or admission decisions. Triggers on `external_policy_server`, `/api/admin/configuration/v1/external_policy_server/`, `policy_request`, `service_lookup`, `participant_properties_lookup`, "external policy", "policy server", "custom call routing". Do NOT use for static dial-plan rules (use `pexip-operations/dial-plan.md`) or runtime commands (use `pexip-command-api`).
license: MIT
---

# Pexip External Policy Server

The **External Policy API** allows Pexip Infinity Conferencing Nodes to outsource call-routing, authentication, and admission control decisions to an external HTTP service. When enabled, Pexip queries your policy server at call setup and applies the returned rules, bypassing or augmenting Pexip's internal configuration database.

## Quick reference

- **Protocol**: HTTP/HTTPS (HTTPS recommended for production)
- **Method**: `GET` (Conferencing Nodes query the server using URL parameters)
- **Timeout**: 5 seconds (non-configurable). A timeout or non-200 response triggers local fallback.
- **Mutual TLS**: Supported by uploading client/server CA certificates.
- **Base Response Wrapper**:
  ```json
  {
    "status": "success",
    "action": "continue|reject|redirect",
    "result": { ... }
  }
  ```

---

## Hook points & URI paths

### 1. Service Configuration
* **URI Path**: `GET /policy/v1/service/configuration`
* **Triggered**: When an incoming call arrives or Pexip needs to dial out.
* **Key Request Parameters**: `local_alias`, `remote_alias`, `protocol` (sip, h323, webrtc, api), `call_direction` (dial_in, dial_out, non_dial), `bandwidth`, `node_ip`, `location`.
* **Actions**:
  - `continue`: Look up the alias in Pexip's local database.
  - `reject`: Block the call immediately (returns "conference not found").
  - `redirect`: Redirect endpoints using SIP 302. Returns `"result": {"new_alias": "sip:redirect-target@example.com"}`.
* **Result Payload (on success)**: Replaces/sets properties of the target service (VMR, Gateway, etc.):
  ```json
  {
    "status": "success",
    "action": "continue",
    "result": {
      "name": "Dynamic VMR",
      "service_type": "conference",
      "service_uuid": "12345678-abcd-1234-abcd-1234567890ab",
      "pin": "1234",
      "guest_pin": "5678",
      "allow_guests": true,
      "description": "Dynamically routed room"
    }
  }
  ```

### 2. Participant Properties
* **URI Path**: `GET /policy/v1/participant/properties`
* **Triggered**: Applied before a participant joins the conference. For WebRTC, this runs *after* PIN entry/SSO, giving access to Identity Provider metadata.
* **Result Payload**: Allows modifying display name, role, or media limits:
  ```json
  {
    "status": "success",
    "result": {
      "display_name": "Anonymized Guest",
      "role": "guest",
      "service_name": "Conf-123",
      "rx_presentation_policy": "ALLOW"
    }
  }
  ```

### 3. Media Location
* **URI Path**: `GET /policy/v1/participant/location`
* **Triggered**: During call setup to determine which system location handles participant media.
* **Key Request Parameters**: `remote_alias`, `local_alias`, `protocol`, `node_ip`.
* **Result Payload**:
  ```json
  {
    "status": "success",
    "result": {
      "location": "Dallas-Data-Center"
    }
  }
  ```

### 4. Registration Alias
* **URI Path**: `GET /policy/v1/registrations/<alias>`
* **Triggered**: When an endpoint attempts to register with Pexip.
* **Actions**:
  - `continue`: Let Pexip match registration credentials against local configuration.
  - `reject`: Deny registration immediately.
* **Result Payload**:
  ```json
  {
    "status": "success",
    "action": "continue"
  }
  ```

### 5. Directory Information
* **URI Path**: `GET /policy/v1/registrations`
* **Triggered**: When Pexip apps request phonebook/directory contact data.
* **Result Payload**:
  ```json
  {
    "status": "success",
    "result": {
      "contacts": [
        { "name": "Main Office VMR", "alias": "main-office@example.com" },
        { "name": "IT Support VMR", "alias": "it-support@example.com" }
      ]
    }
  }
  ```

### 6. Participant Avatar
* **URI Path**: `GET /policy/v1/participant/avatar/<alias>`
* **Triggered**: When Pexip needs to retrieve an image representation for a participant or directory contact.
* **Response Requirements**: Returns the binary payload directly with a `Content-Type` of `image/jpeg` or `image/png`. Returning a `404 Not Found` will cause Pexip to fall back to the default local user avatar.

---

## Gotchas and constraints

- **Synchronous Call Blocking**: The policy server is in the synchronous call path. The 5-second timeout exists to prevent call locks. Your policy server must respond within milliseconds to ensure a smooth user setup experience.
- **Fail-Safe Fallback**: If your policy server goes offline, Pexip automatically falls back to its local database lookup. Ensure that fallback dial-plan rules are configured locally in Pexip for critical calls.
- **Field Limit**: All strings inside the JSON `result` block are capped at a maximum of 250 characters.
- **Client redirects**: Pexip does **not** follow HTTP 301/302 redirects returned by the policy server. All responses from the policy server must use the status code `200 OK` (with the exception of returning 404 for avatar fallbacks).

## Reference source

- **Authoritative Pexip docs:**
  - External policy overview: https://docs.pexip.com/admin/external_policy.htm
  - Requests/responses schema: https://docs.pexip.com/admin/external_policy_requests.htm
  - API reference: https://docs.pexip.com/api_manage/api_external_policy.htm
- **Related skills:**
  - Config API: [pexip-config-api](../../management-api/pexip-config-api/SKILL.md)
  - Dial plan: `pexip-operations/dial-plan.md`
  - Event webhooks: [pexip-event-sinks](../../events/pexip-event-sinks/SKILL.md)
