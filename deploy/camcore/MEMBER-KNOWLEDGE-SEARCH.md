# Member knowledge search fallback

CamCore Private chat searches Outline server-side for explicitly CamCore-related questions.

If the conversational question returns no usable Outline match, Jarvis now retries once with a focused query built from the salient non-stopword terms. For example, `What is Earth in CamCore?` retries as `Earth`.

This does not change the member security boundary: the model still receives no MCP tool schemas, Outline credentials, administrative memory, write tools, private addresses, private `camcore.network` hostnames, or secret-bearing lines.

Jarvis logs only non-sensitive lookup diagnostics such as tool availability, match counts, retry state, fetch errors, and whether a context block was built. It does not log retrieved document contents.