# Focused member knowledge production verification

After deploying this change, test Private chat with:

> What is Earth in CamCore?

If the initial conversational Outline query finds no usable documentation, the Jarvis log should show a focused-search retry and then a non-zero document-match count when an Earth document exists.

The answer should use the documented high-level role and must not expose credentials, private addresses, private `camcore.network` hostnames, administrative memory, or live-state claims.