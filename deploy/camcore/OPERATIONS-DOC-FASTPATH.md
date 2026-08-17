# CamCore Operations documentation fast path

When Operations receives a CamCore documentation question and the trusted server-side Outline prefetch returns current documentation, Jarvis treats simple answer-only lookups differently from operational actions.

For answer-only documentation lookups, the model receives the freshly fetched, sanitised Outline context with no callable Operations tool schema and a one-turn limit. This prevents small local models from entering unnecessary tool loops when the authoritative answer is already present.

Explicit operational actions and live-state questions retain the normal Operations tool set. Raw Outline MCP tools remain server-side only.
