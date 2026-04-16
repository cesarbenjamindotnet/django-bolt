# Server-Sent Events (SSE)

Server-Sent Events is a standard for pushing real-time updates from server to client over HTTP. Django-Bolt provides `EventSourceResponse` with automatic SSE framing, compression skipping, and keep-alive pings.

## Quick start

```python
from collections.abc import AsyncIterable
from django_bolt import BoltAPI
from django_bolt.responses import EventSourceResponse

api = BoltAPI()

@api.get("/events", response_class=EventSourceResponse)
async def events() -> AsyncIterable[dict]:
    for i in range(10):
        yield {"count": i}
        await asyncio.sleep(1)
```

That's it. Yielded objects are automatically:

- JSON-serialized
- Wrapped in SSE `data:` framing
- Sent without compression (handled at the Rust level)
- Kept alive with `: ping` comments every 15 seconds

## Two patterns

### Implicit (recommended)

The handler itself is a generator. Set `response_class=EventSourceResponse` on the decorator:

```python
@api.get("/prices", response_class=EventSourceResponse)
async def stock_prices() -> AsyncIterable[StockPrice]:
    while True:
        yield StockPrice(symbol="AAPL", price=await get_price("AAPL"))
        await asyncio.sleep(1)
```

Works with any serializable type: dicts, msgspec Structs, lists.

### Explicit

Return `EventSourceResponse` directly when you need control over status code, headers, or ping interval:

```python
from django_bolt.responses import EventSourceResponse

@api.get("/stream")
async def stream():
    async def generate():
        yield {"message": "hello"}
        yield {"message": "world"}

    return EventSourceResponse(generate(), ping_interval=30.0)
```

## ServerSentEvent

For full control over SSE fields (event type, ID, retry, comments), yield `ServerSentEvent` objects:

```python
from django_bolt.responses import EventSourceResponse, ServerSentEvent

@api.get("/sse-events", response_class=EventSourceResponse)
async def sse_events() -> AsyncIterable[ServerSentEvent]:
    for i in range(5):
        yield ServerSentEvent(
            data={"count": i},
            event="update",
            id=str(i),
        )
        await asyncio.sleep(0.5)
```

Client receives:

```
event: update
data: {"count":0}
id: 0

event: update
data: {"count":1}
id: 1
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data` | `Any` | `None` | JSON-serialized event payload |
| `raw_data` | `str \| None` | `None` | Raw string payload (mutually exclusive with `data`) |
| `event` | `str \| None` | `None` | Event type (maps to `addEventListener` in browser) |
| `id` | `str \| None` | `None` | Event ID for reconnection (`Last-Event-ID` header) |
| `retry` | `int \| None` | `None` | Reconnection time in milliseconds |
| `comment` | `str \| None` | `None` | Comment line (`: ` prefix, ignored by EventSource clients) |

### Mixing yield types

You can mix plain objects and `ServerSentEvent` in a single stream:

```python
@api.get("/mixed", response_class=EventSourceResponse)
async def mixed():
    yield {"status": "started"}                          # auto-framed as data:
    yield ServerSentEvent(data={"n": 1}, event="tick")   # full SSE event
    yield ServerSentEvent(comment="keepalive")            # comment only
    yield ServerSentEvent(data="done", event="complete")  # string data
```

### raw_data

Use `raw_data` to send pre-formatted strings without JSON encoding:

```python
yield ServerSentEvent(raw_data="plain text line")
# Produces: data: plain text line
```

Compare with `data`:

```python
yield ServerSentEvent(data="plain text line")
# Produces: data: "plain text line"   (JSON-encoded with quotes)
```

## Sync generators

Both sync and async generators work:

```python
@api.get("/sync-sse", response_class=EventSourceResponse)
def sync_sse():
    for i in range(5):
        yield {"sync_message": i}
        time.sleep(0.1)
```

## Cleanup on disconnect

Use try/finally for resource cleanup when clients disconnect:

```python
@api.get("/sse-with-cleanup", response_class=EventSourceResponse)
async def sse_with_cleanup():
    try:
        yield {"status": "START"}
        for i in range(100):
            yield {"chunk": i}
            await asyncio.sleep(0.1)
    finally:
        print("Client disconnected, cleaning up")
```

## Keep-alive pings

`EventSourceResponse` sends `: ping` comments every 15 seconds when the generator is idle. This prevents proxies and load balancers from closing the connection.

Configure or disable:

```python
# Custom interval (seconds)
return EventSourceResponse(generate(), ping_interval=30.0)

# Disable keep-alive
return EventSourceResponse(generate(), ping_interval=None)
```

Keep-alive runs in Rust — no GIL overhead.

## Compression

`EventSourceResponse` automatically skips compression. Compression buffers the entire response before sending, which defeats streaming. No `@no_compress` decorator needed.

This also applies to legacy `StreamingResponse(media_type="text/event-stream")` — all SSE streams skip compression automatically at the Rust level.

## EventSourceResponse parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | generator | required | Generator instance |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Additional response headers |
| `ping_interval` | `float \| None` | `15.0` | Keep-alive interval in seconds (`None` to disable) |

## format_sse_event

Low-level function to build SSE wire-format bytes manually:

```python
from django_bolt.responses import format_sse_event

# Data-only event
format_sse_event(data_str='{"count": 1}')
# b'data: {"count": 1}\n\n'

# Pre-encoded bytes (avoids decode/encode round-trip)
format_sse_event(data_bytes=b'{"count": 1}')
# b'data: {"count": 1}\n\n'

# Full event with all fields
format_sse_event(data_str="payload", event="update", id="42", retry=5000)
# b'event: update\ndata: payload\nid: 42\nretry: 5000\n\n'
```

## Raw SSE with StreamingResponse

If you need manual control over SSE wire framing, use `StreamingResponse` directly:

```python
from django_bolt import StreamingResponse
from django_bolt.middleware import no_compress

@api.get("/raw-sse")
@no_compress
async def raw_sse():
    async def generate():
        for i in range(10):
            yield f"event: update\nid: {i}\ndata: {{\"count\": {i}}}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

!!! note
    With `StreamingResponse` you must manually format SSE frames and add `@no_compress`.
    Prefer `EventSourceResponse`.

## Testing

```python
from django_bolt import BoltAPI
from django_bolt.responses import EventSourceResponse
from django_bolt.testing import TestClient

api = BoltAPI()

@api.get("/sse", response_class=EventSourceResponse)
async def sse():
    yield {"message": "hello"}
    yield {"message": "world"}

with TestClient(api) as client:
    response = client.get("/sse")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.content.decode()
    assert 'data: {"message":"hello"}' in body
    assert 'data: {"message":"world"}' in body
```
