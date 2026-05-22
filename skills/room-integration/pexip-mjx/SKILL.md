---
name: pexip-mjx
description: Configure and extend Pexip's MJX (Microsoft Join eXchange, One-Touch Join) calendar integration — the feature that pulls calendar data from Exchange/Google Workspace and pushes "Join" buttons to in-room video systems. Triggers on `mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`, `one-touch join`, "OTJ", "in-room join", "Exchange room mailbox", "calendar integration". Do NOT use for general client-side WebRTC join flows (use pexip-call-lifecycle) or local room system hardware macros/controls (use pexip-room-integration).
license: MIT
---

# Pexip MJX — One-Touch Join for room systems

**MJX (Microsoft Join eXchange)** is Pexip's integration for scheduled room meetings (often called One-Touch Join or OTJ). It reads from room calendars (Exchange or Google Workspace), parses invitation bodies to identify video conference links, and pushes a "Join" button to the in-room touch panel.

---

## Calendar integrations & authorization

MJX connects to calendar servers using three deployment resource types:

### 1. Microsoft 365 / Exchange Online (Graph API)
* **Resource Path**: `/api/admin/configuration/v1/mjx_graph_deployment/`
* **OAuth Scopes**: Requires Microsoft Graph Application permission `Calendars.Read`.
* **Flow**: Uses client ID, tenant ID, and client secret with OAuth 2.0 to access room resource mailboxes.

### 2. Exchange On-Premises (EWS)
* **Resource Path**: `/api/admin/configuration/v1/mjx_exchange_deployment/`
* **Authentication**: Requires Exchange Web Services (EWS) Impersonation or a service account with `ApplicationImpersonation` rights to read calendar folders on room mailboxes.
* **Autodiscover**: Configured using `/api/admin/configuration/v1/mjx_exchange_autodiscover_url/`.

### 3. Google Workspace (Google Calendar API)
* **Resource Path**: `/api/admin/configuration/v1/mjx_google_deployment/`
* **Authentication**: Uses a Google Service Account key file (.json) with Domain-Wide Delegation (DwD) to impersonate room mailboxes, or direct calendar sharing if DwD is disabled.
* **Scope**: `https://www.googleapis.com/auth/calendar.readonly`

---

## Processing rules (Regex parsing)

To identify meetings, Pexip evaluates the invite body against regex patterns configured under `/api/admin/configuration/v1/mjx_meeting_processing_rule/`.

| Target Service | Match Regex Pattern | Dial Template | Protocol |
|---|---|---|---|
| **Pexip VMR** | `meet\.example\.com/([a-z0-9._-]+)` | `\1@meet.example.com` | `sip` |
| **MS Teams CVI** | `teams\.microsoft\.com/l/meetup-join/([a-zA-Z0-9%_-]+)` | `\1@teams.example.com` | `sip` |
| **Zoom CVI** | `zoom\.us/j/([0-9]+)\?pwd=([a-zA-Z0-9]+)` | `\1.\2@zoomcrc.com` | `sip` |
| **Google Meet** | `meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})` | `\1@gmeet.example.com` | `sip` |

*Note: Ensure CVI (Cloud Video Interop) suffixes match your specific tenant's routing rules.*

---

## Endpoint push mechanics

Once a meeting is parsed and a dial string is produced, Pexip connects to room systems configured under `/api/admin/configuration/v1/mjx_endpoint/` to push the Join payload.

* **Cisco CE/RoomOS**: Pexip uses SSH or HTTP xAPI to push the booking payload. The endpoint must have local xAPI/http access enabled.
* **Poly Trio/G7500**: Pexip pushes the calendar JSON payload using the Poly REST API on HTTPS (port 443).
* **Logitech Tap (CollabOS)**: Pexip pushes booking updates to the sync agent API.

---

## Troubleshooting & diagnostics

All MJX operations are logged to the Management Node. Check support logs under the `support.otj` module:

- **Create Event**: `Message="OTJ Meeting Created" Room="roomresource@example.com" Subject="Project Sync" Alias="1234@pexip.com" OTJRuleName="Pexip Rule"`
- **Change Event**: `Message="OTJ Meeting Changed"` (fired on rescheduling or changing VMR).
- **Delete Event**: `Message="OTJ Meeting Deleted"` (fired when the invite is canceled).

### Common failure modes

1. **Authentication Failures (401/403)**:
   - *Exchange/Graph*: Invalid Client Secret or expired OAuth application credentials.
   - *Google*: Service Account key JSON deleted, or API Access Control missing OAuth Client ID scope delegation in Google Admin console.
2. **Autodiscover Errors**: Autodiscover DNS SRV records (`_autodiscover._tcp.<domain>`) not reachable from the Pexip Management Node.
3. **No Join Button on Touch Panel**:
   - The regex rule failed to match the invitation body text. Verify by checking if `support.otj` logs the meeting creation but without matching a rule.
   - Device credentials in `/api/admin/configuration/v1/mjx_endpoint/` are incorrect, blocking the push command.

## Reference source

- **Authoritative Pexip docs:**
  - MJX (One-Touch Join) overview: https://docs.pexip.com/admin/mjx_intro.htm
  - Configuring MJX: https://docs.pexip.com/admin/configuring_mjx.htm
  - API configuration reference: https://docs.pexip.com/api_manage/api_configuration.htm
- **Related skills:**
  - Room integration: [pexip-room-integration](../../room-integration/pexip-room-integration/SKILL.md)
  - Config API: [pexip-config-api](../../management-api/pexip-config-api/SKILL.md)
  - Operations dial plan: `pexip-operations/dial-plan.md`
