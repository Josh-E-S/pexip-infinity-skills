# Pexip Event Sink — Production Receiver Patterns

Production-grade receiver architectures for Pexip webhook events. See [`SKILL.md`](SKILL.md) for configuration, envelope format, and field reference.

## Pattern 1: Node.js / TypeScript (Express + Redis)

Sub-millisecond response times. Verifies Basic Auth, normalizes bulk/single payloads, deduplicates on `(node, seq, time)`, and offloads events to a Redis queue for background workers.

```typescript
import express, { Request, Response } from 'express';
import Redis from 'ioredis';

const app   = express();
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
app.use(express.json());

const basicAuth = (req: Request, res: Response, next: Function) => {
    const [type, credentials] = (req.headers.authorization || '').split(' ');
    if (type?.toLowerCase() !== 'basic' || !credentials) return res.status(401).send('Unauthorized');
    const [username, password] = Buffer.from(credentials, 'base64').toString().split(':');
    if (username !== process.env.WEBHOOK_USER || password !== process.env.WEBHOOK_PASS) return res.status(401).send('Unauthorized');
    next();
};

app.post('/webhook/pexip-events', basicAuth, async (req: Request, res: Response) => {
    // Acknowledge immediately — slow response causes Pexip node queue backup
    res.status(200).json({ status: 'accepted' });

    const payload = req.body;
    const events: any[] = payload.event === 'eventsink_bulk' ? (payload.data || []) : payload.event ? [payload] : [];

    for (const event of events) {
        // Dedup key: (node, seq, floor(time)) — seq resets to 1 on sink restart
        const dedupeKey = `pexip:event:${event.node}:${event.seq}:${Math.floor(event.time)}`;
        const isUnique  = await redis.set(dedupeKey, '1', 'NX', 'EX', 86400);
        if (isUnique) {
            await redis.rpush('pexip:queue:events', JSON.stringify(event));
        }
    }
});

app.listen(3000);
```

## Pattern 2: Python (FastAPI + BackgroundTasks)

Responds instantly, processes out of the request thread. Handles out-of-order events using per-resource timestamp tracking.

```python
import os, secrets
from fastapi import FastAPI, Request, Response, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import redis

app      = FastAPI()
security = HTTPBasic()
r        = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, os.environ["WEBHOOK_USER"]) and \
         secrets.compare_digest(credentials.password, os.environ["WEBHOOK_PASS"])
    if not ok:
        raise HTTPException(status_code=401)

def process_event(event: dict):
    resource_id = event.get("data", {}).get("participant_uuid") or event.get("data", {}).get("conversation_id")
    if resource_id:
        key        = f"pexip:state:timestamp:{resource_id}"
        event_time = float(event.get("time", 0))
        last_time  = r.get(key)
        if last_time and float(last_time) >= event_time:
            return  # out-of-order — discard
        r.set(key, str(event_time), ex=86400)
    # write to DB / warehouse / SIEM here
    print(f"Processed: {event.get('event')} seq={event.get('seq')}")

@app.post("/webhook/pexip-events", dependencies=[Depends(verify_credentials)])
async def receive_events(request: Request, background_tasks: BackgroundTasks):
    body   = await request.json()
    events = body.get("data", []) if body.get("event") == "eventsink_bulk" else [body]

    for ev in events:
        dedupe_key = f"pexip:event:{ev.get('node')}:{ev.get('seq')}:{int(float(ev.get('time', 0)))}"
        if r.set(dedupe_key, "1", nx=True, ex=86400):
            background_tasks.add_task(process_event, ev)

    return Response(status_code=200, content='{"status":"accepted"}', media_type="application/json")
```

## Idempotency & out-of-order delivery

### Idempotency key

`(node, seq, Math.floor(time))` uniquely identifies any event from a Conferencing Node. With `bulk_support=True`, evaluate each child event individually — the bulk wrapper itself is not the unit of deduplication.

### Out-of-order events

Nodes process events independently; `participant_disconnected` can arrive before a delayed `participant_connected`.

**Rule:** before applying state changes, compare `event.time` with your stored `last_updated` for that resource. If `event.time < last_updated`, discard. Only apply if strictly newer.

### Seq resets

`seq` restarts at `1` when a sink is stopped and restarted on a node. Pair `eventsink_started` with the immediately following `seq=1` to detect a reset cleanly rather than treating it as a duplicate.
