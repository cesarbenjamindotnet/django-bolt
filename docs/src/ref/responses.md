---
icon: lucide/send
---

# Responses Reference

This page documents all response types available in Django-Bolt.

## Response

Generic response with custom headers.

```python
from django_bolt import Response

return Response(
    {"data": "value"},
    status_code=200,
    headers={"X-Custom": "header"}
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `Any` | `{}` | Response content |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |
| `media_type` | `str` | `"application/json"` | Content type |

## JSON

Explicit JSON response with status and headers.

```python
from django_bolt import JSON

return JSON(
    {"id": 1, "name": "Item"},
    status_code=201,
    headers={"X-Created": "true"}
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `Any` | required | JSON-serializable data |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |

## PlainText

Plain text response.

```python
from django_bolt.responses import PlainText

return PlainText("Hello, World!")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | required | Text content |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |

## HTML

HTML response.

```python
from django_bolt.responses import HTML

return HTML("<h1>Hello</h1>")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `html` | `str` | required | HTML content |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |

## Redirect

HTTP redirect response.

```python
from django_bolt.responses import Redirect

return Redirect("/new-location")
return Redirect("/new-location", status_code=301)  # Permanent
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | required | Redirect URL |
| `status_code` | `int` | `307` | Redirect status code |
| `headers` | `dict` | `None` | Response headers |

### Status codes

| Code | Description |
|------|-------------|
| `301` | Permanent redirect |
| `302` | Found (temporary) |
| `303` | See Other |
| `307` | Temporary redirect (preserves method) |
| `308` | Permanent redirect (preserves method) |

## File

In-memory file download.

```python
from django_bolt.responses import File

return File(
    "/path/to/file.pdf",
    filename="document.pdf",
    media_type="application/pdf"
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | File path |
| `filename` | `str` | `None` | Download filename |
| `media_type` | `str` | `None` | Content type |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |

## FileResponse

Streaming file response for large files.

```python
from django_bolt.responses import FileResponse

return FileResponse(
    "/path/to/large-video.mp4",
    filename="video.mp4"
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | File path |
| `filename` | `str` | `None` | Download filename |
| `media_type` | `str` | `None` | Content type (auto-detected) |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Response headers |

### Security

Configure allowed directories in `settings.py`:

```python
BOLT_ALLOWED_FILE_PATHS = [
    "/var/app/uploads",
]
```

## EventSourceResponse

Server-Sent Events response with automatic SSE framing, compression skipping, and keep-alive pings. See the [SSE topic guide](../topics/sse.md) for full documentation.

### Implicit pattern

```python
from collections.abc import AsyncIterable
from django_bolt.responses import EventSourceResponse

@api.get("/events", response_class=EventSourceResponse)
async def events() -> AsyncIterable[dict]:
    for i in range(10):
        yield {"count": i}
        await asyncio.sleep(1)
```

### Explicit pattern

```python
from django_bolt.responses import EventSourceResponse

@api.get("/events")
async def events():
    async def generate():
        yield {"count": i}
    return EventSourceResponse(generate())
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | generator | required | Generator instance |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `dict` | `None` | Additional response headers |
| `ping_interval` | `float \| None` | `15.0` | Keep-alive ping interval in seconds (`None` to disable) |

### Automatic behavior

- **SSE framing**: Yielded objects are JSON-serialized and wrapped in `data: ...\n\n`
- **Compression**: Automatically skipped (no `@no_compress` needed)
- **Headers**: `Cache-Control`, `X-Accel-Buffering`, `Content-Type` set automatically
- **Keep-alive**: `: ping` comments sent when idle to prevent proxy timeouts

## ServerSentEvent

Represents a single SSE event with full control over all fields.

```python
from django_bolt.responses import ServerSentEvent

yield ServerSentEvent(data={"count": 1}, event="update", id="1")
yield ServerSentEvent(raw_data="plain text", comment="keepalive")
yield ServerSentEvent(retry=5000)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data` | `Any` | `None` | JSON-serialized event payload |
| `raw_data` | `str \| None` | `None` | Raw string payload (mutually exclusive with `data`) |
| `event` | `str \| None` | `None` | Event type name |
| `id` | `str \| None` | `None` | Event ID (no null characters) |
| `retry` | `int \| None` | `None` | Reconnection time in ms (non-negative) |
| `comment` | `str \| None` | `None` | Comment line (`: ` prefix) |

## format_sse_event

Build SSE wire-format bytes from pre-serialized data.

```python
from django_bolt.responses import format_sse_event

# Simple data event
frame = format_sse_event(data_str='{"count": 1}')
# b'data: {"count": 1}\n\n'

# Full event
frame = format_sse_event(data_str="payload", event="update", id="42", retry=5000)
# b'event: update\ndata: payload\nid: 42\nretry: 5000\n\n'

# Pre-encoded bytes (avoids decode/encode round-trip)
frame = format_sse_event(data_bytes=b'{"count": 1}')
# b'data: {"count": 1}\n\n'
```

## StreamingResponse

General-purpose streaming response for generators.

```python
from django_bolt import StreamingResponse

def generate():
    for i in range(100):
        yield f"chunk {i}\n"

return StreamingResponse(generate(), media_type="text/plain")
```

### Async generators

```python
async def async_generate():
    for i in range(100):
        await asyncio.sleep(0.1)
        yield f"chunk {i}\n"

return StreamingResponse(async_generate(), media_type="text/plain")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | generator | required | Generator instance |
| `status_code` | `int` | `200` | HTTP status code |
| `media_type` | `str` | `"application/octet-stream"` | Content type |
| `headers` | `dict` | `None` | Response headers |

### Common media types

| Type | Use case |
|------|----------|
| `text/plain` | Plain text streaming |
| `text/event-stream` | Server-Sent Events (prefer `EventSourceResponse`) |
| `application/octet-stream` | Binary data |
| `application/json` | JSON streaming (NDJSON) |

## Implicit responses

### Dict/list

Returns JSON with status 200.

```python
return {"message": "Hello"}
return [{"id": 1}, {"id": 2}]
```

### String

Returns plain text with status 200.

```python
return "Hello, World!"
```

### Bytes

Returns binary with `application/octet-stream`.

```python
return b"\x00\x01\x02\x03"
```

### msgspec.Struct

Returns JSON with automatic serialization.

```python
import msgspec

class User(msgspec.Struct):
    id: int
    name: str

return User(id=1, name="John")
```
