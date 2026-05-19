# Recipe: bootstrap a webhook event collector

End-to-end workflow for moving from "poll the History API for CDRs" to "Pexip pushes events to my collector in real time". Configures the Pexip side via the MCP server and provides a receiver skeleton you can deploy anywhere.

**Skills used:** `pexip-event-sinks`, `pexip-config-api`.

## Inputs

- `name` — event sink display name (e.g. `cdr-collector`).
- `receiver_url` — public HTTPS URL of your collector (e.g. `https://cdr.example.com/pexip-events`).
- `basic_auth` (optional) — `(username, password)` Pexip will send with each POST.
- `verify_tls` — default `true`. Only set false for self-signed lab certs.

## Steps

### 1. Stand up the receiver FIRST

Bring the HTTP listener online BEFORE registering the sink. If Pexip pushes to a URL that 404s or times out, it'll retry and eventually drop — and the gap is a hassle to backfill.

Minimal Python receiver (FastAPI):

```python
# receiver.py
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets, json, os

app = FastAPI()
security = HTTPBasic()
USER = os.environ["WEBHOOK_USER"]
PASS = os.environ["WEBHOOK_PASS"]

def verify(creds: HTTPBasicCredentials = Depends(security)):
    ok = (secrets.compare_digest(creds.username, USER) and
          secrets.compare_digest(creds.password, PASS))
    if not ok:
        raise HTTPException(401)

@app.post("/pexip-events", dependencies=[Depends(verify)])
async def receive(request: Request):
    body = await request.json()
    # Pexip sends either a single event object or (if bulk_support=True) a list.
    events = body if isinstance(body, list) else [body]
    for ev in events:
        # Idempotent write — dedupe by event id, or by (call_id, event_type, ts).
        await persist(ev)
    return Response(status_code=200)

async def persist(ev):
    # Replace with your queue/warehouse — Kafka, SQS, Redis Streams, BigQuery, …
    print(json.dumps(ev))
```

Deploy on whatever you have — Fly, Cloud Run, Lambda+API Gateway, your existing app server. Requirements:

- **HTTPS** with a valid cert (or test with `verify_tls=False` against the sink for a self-signed lab).
- **2xx response within Pexip's timeout** (a few seconds; check current Pexip docs for the exact value).
- **Reachable from every Conferencing Node**, not just the Management Node.

### 2. Register the event sink

```
sink = create_event_sink(
    name         = name,
    url          = receiver_url,
    version      = 2,              # current event protocol version
    bulk_support = True,           # Pexip batches; your receiver above handles both
    verify_tls   = True,           # set False only for self-signed lab cert
    username     = basic_auth[0] if basic_auth else None,
    password     = basic_auth[1] if basic_auth else None,
    description  = f"Receiver at {receiver_url}",
)
```

Verify Pexip persisted it:

```
get_event_sink(sink=name)
```

The response will have `username` masked / null (write-only field) — that's expected.

### 3. Trigger a test event

Easiest test: dial into any VMR. The `participant_connected` event should hit your receiver within seconds.

If nothing arrives:

- Check the receiver's logs for incoming requests at all.
- Verify the URL is reachable from a Conferencing Node (not just from your laptop).
- Check Pexip's admin UI under **History & Statistics → Event Sinks** for delivery errors.
- Confirm `verify_tls` matches your cert situation (lots of "events not arriving" cases are TLS handshake failures Pexip retries silently for a while).

### 4. Add a reconciliation job

Event sinks can lose events (receiver downtime, retry budget exhaustion). Run a periodic reconcile from the History API to fill gaps:

```python
# reconcile.py — run hourly via cron
import datetime
from pexip_mcp_client import client      # or call the MCP tools via Claude/your agent

last_seen = read_watermark()             # from your store
now       = datetime.datetime.utcnow().replace(microsecond=0)

backfill = client.list_history_participants(
    start_time = last_seen.isoformat(),
    end_time   = now.isoformat(),
    fetch_all  = True,
)

for record in backfill["objects"]:
    if not already_persisted(record["id"]):
        persist_from_history(record)

write_watermark(now)
```

Idempotency on `record["id"]` is what lets event-push and history-pull coexist cleanly.

### 5. Document the sink

Keep a doc/page somewhere with:

- The sink's `name` and `id` in Pexip
- Receiver hostname / repo / deployment
- Basic auth credentials (in your secrets manager, NOT in the doc itself)
- Owner contact for when something breaks at 3am

## Variations

### Move to push-only (decommission History polling)

Once the collector has weeks of clean overlap with History API polls, you can stop polling. Keep the reconcile job — it covers cases where the receiver is down.

### Multiple sinks

Pexip supports multiple event sinks. Useful for splitting traffic: one to a long-term warehouse, one to a real-time alerting pipeline. Just call `create_event_sink` again with different `name` + `url`.

## Safety

- **Receiver-side**: bullets in step 1 are non-negotiable for production. A receiver that returns 500 on every event will hammer Pexip's retry queue and eventually start dropping.
- **Credentials**: don't put basic auth credentials in shell history or git. Use env vars / secrets manager.
- **TLS verification off** is a real risk — events contain participant identifiers (display names, addresses) and call metadata. Get a real cert.

## Reference source

- Skill: `pexip-event-sinks`
- MCP tools: `list_event_sinks`, `create_event_sink`, `update_event_sink`, `delete_event_sink`, `get_event_sink` in `src/pexip_mcp/tools/event_sink.py`
- Pexip docs: https://docs.pexip.com/admin/event_sink.htm
- Parent repo's roadmap sketch for a hosted receiver: `TODO.md` in `pexip-mgmt-mcp`
