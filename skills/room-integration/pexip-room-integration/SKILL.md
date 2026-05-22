---
name: pexip-room-integration
description: Hardware-level room system integrations (Cisco RoomOS, Poly Trio, Crestron, Q-SYS, Logitech) with Pexip Infinity. Use when writing Cisco macros, Poly REST API scripts, or Crestron/Q-SYS Lua scripts to control endpoint layouts, handle local mute states, or listen to Pexip events. Covers xAPI command mappings, local API setups, and custom room control UI development. Do NOT use for calendar-driven One-Touch Join (use pexip-mjx) or general client-side WebRTC plugins (use pexip-call-lifecycle).
license: MIT
---

# Pexip Room Integration — Cisco, Poly, Crestron & Q-SYS

This skill covers the integration of hardware meeting room endpoints with Pexip Infinity. By using local device APIs, custom macros, and control systems, you can synchronize room states (like local mute, camera control, and UI feedback) with Pexip calls.

## Quick reference

| System | Protocol / Tool | Common Use Case |
|---|---|---|
| **Cisco RoomOS** | xAPI / JavaScript Macros | Custom buttons, call state listening, local layout adjustments |
| **Poly Trio / Group** | REST API / Web Server | Remote mute sync, status polling, dial control |
| **Crestron / Q-SYS** | Lua / TCP/HTTP client | Room controller touchpanel integration with Pexip APIs |
| **Logitech CollabOS** | REST / local management | Device state monitoring and configuration |

## When to use

- "Write a Cisco macro that reacts to a Pexip conference starting"
- "Synchronize our Q-SYS/Crestron mute button with the Pexip conference mute state"
- "Trigger Poly endpoint functions programmatically during a call"
- "Map custom touchpanel buttons to Pexip in-call DTMF or layout commands"
- "Control local cameras or active speaker tracking based on Pexip API responses"

## When NOT to use

- Configuring calendar One-Touch Join (OTJ / OBTP) → use [pexip-mjx](../../room-integration/pexip-mjx/SKILL.md)
- Setting up server-side webhook notification push targets → use [pexip-event-sinks](../../events/pexip-event-sinks/SKILL.md)
- In-browser WebRTC client controls or layout modifications → use `pexip-call-lifecycle` or `pexip-layouts` under `skills/client/`

## Cisco RoomOS Macros (xAPI)

Cisco Webex Room devices run RoomOS and support local JavaScript macros. These macros run directly on the device and can interact with the Pexip service using the `xapi` object and the `HttpClient` module.

### Subscribing to Call Events
To trigger behavior when a Pexip call starts or ends, listen to call status changes:

```javascript
const xapi = require('xapi');

xapi.Status.Call.on((call) => {
  if (call.Status === 'Connected') {
    console.log('Call connected to: ' + call.RemoteNumber);
    // Execute custom logic (e.g., lower local blinds, adjust lights)
  }
});
```

### Sending HTTP Commands to Pexip
RoomOS macros can post status updates or trigger Pexip Management/Client APIs via `xapi.command('HttpClient Post', ...)`:

```javascript
xapi.Config.HttpClient.Mode.set('On');
xapi.Config.HttpClient.AllowInsecureHTTPS.set('On'); // For labs only

xapi.command('HttpClient Post', {
  Url: 'https://pexip-node.example.com/api/client/v2/conferences/ VMR_NAME/participants/PARTICIPANT_ID/mute',
  Header: ['Content-Type: application/json', 'Authorization: Bearer TOKEN'],
  Body: JSON.stringify({ mute: true })
});
```

## Poly REST API & Control

Poly endpoints (Trio, G7500, Studio X) expose a local REST API that must be enabled in the device web interface.

### Example: Polling and Remote Mute
You can toggle or poll the device mute state using REST commands from a control processor:

```bash
# Mute the Poly device locally
curl -k -u admin:password -X POST \
  https://<poly-ip>/rest/conferences/0/mute \
  -H "Content-Type: application/json" \
  -d '{"mute": true}'
```

To sync with Pexip, the controller can query Pexip's live participant list and apply the mute state locally via this API.

## Crestron and Q-SYS Lua Scripting

Custom room control systems connect to Pexip endpoints or room systems via TCP/IP sockets or HTTP clients. In Q-SYS, you write Lua scripts to drive room status.

### Q-SYS Lua HTTP Client Example
To sync room controller buttons with Pexip, use the Q-SYS `HttpClient` library:

```lua
HttpClient.Upload({
  Url = "https://pexip-node.example.com/api/client/v2/conferences/my-room/mute",
  Method = "POST",
  Headers = { ["Content-Type"] = "application/json" },
  Data = '{"mute": true}',
  EventHandler = function(handler, code, data, err)
    if code == 200 then
      print("Successfully synced mute to Pexip")
    else
      print("Error syncing mute: " .. tostring(err))
    end
  end
})
```

## Gotchas and Common Pitfalls

- **TLS/Certificate Validation**: Hardware room systems are strict about TLS. If using self-signed certificates on local Conferencing Nodes, you must either upload the CA cert to the room system or explicitly set `AllowInsecureHTTPS` / ignore verification (for development only).
- **Control Loop Latency**: Polling the device API too frequently can overload its control processor. Prefer event-based subscriptions (e.g., Cisco's feedback registration) where available.
- **VMR Dial Strings**: Ensure that Cisco/Poly dial rules are configured to send the correct VMR suffix (e.g., `@meet.example.com`) so they route properly through the Pexip Distributed Gateway.

## Reference source

- **Cisco RoomOS Developer Portal:** https://roomos.cisco.com/doc/
- **Poly Developer Guide:** https://docs.poly.com/
- **Pexip Infinity Administration Guide:** https://docs.pexip.com/
- **Related skills:**
  - One-Touch Join: [pexip-mjx](../../room-integration/pexip-mjx/SKILL.md)
  - Webhook delivery: [pexip-event-sinks](../../events/pexip-event-sinks/SKILL.md)
  - Client REST API: `pexip-call-lifecycle` and `pexip-participants` under `skills/client/`
