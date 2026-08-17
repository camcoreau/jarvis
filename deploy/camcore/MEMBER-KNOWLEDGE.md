# Jarvis | CamCore AI — member knowledge boundary

The signed-in CamCore **Private chat** route may use documented CamCore knowledge without giving members the Operations agent, administrative memory, or arbitrary tools.

## Boundary

Member chat remains a direct-model path. The browser and selected model never receive MCP credentials or tool schemas, and the model cannot choose or execute an Outline tool.

For an explicitly CamCore-related question, Jarvis performs a server-side best-effort lookup using only the already configured read-only Outline MCP adapters:

1. `list_documents` searches for relevant documentation.
2. `fetch` reads at most two matching documents.
3. Jarvis extracts only small excerpts relevant to the user's query.
4. The excerpts are sanitised and bounded before they are appended to the member system context.
5. The selected provider then answers from that approved context.

The two tools must be MCP adapters backed by the same MCP client. Same-named internal or unrelated tools are not trusted by this route.

## Information allowed in member answers

Private chat may explain documented, high-level CamCore information such as server names and roles, approved service usage, policies, and general architecture when that information is present in the retrieved member knowledge.

Documentation is reference data only. It is not proof of current service health, reachability, configuration drift, or live operational state.

## Information removed or withheld

Before retrieved text is exposed to the member model, the server removes or redacts common restricted operational data, including:

- credentials, passwords, API keys, bearer/authentication values, private keys and recovery secrets;
- IPv4 network addresses;
- private `*.camcore.network` hostnames/FQDNs;
- email addresses;
- Outline document IDs and internal document URLs from search metadata.

Member chat must also refuse to infer information that was redacted, provide admin-only procedures, expose private monitoring/operational memory, or make changes to CamCore systems.

## Provider privacy

The same boundary applies to Local, OpenAI and Auto modes. Retrieval and sanitisation happen on the Jarvis server first.

When **OpenAI** is the selected provider, only the normal member conversation plus the bounded, sanitised knowledge context may be sent to the OpenAI API. The Outline credential, MCP connection, raw fetched document metadata and administrative Jarvis memory remain server-side.

When **Local** is selected, the same sanitised context is supplied to the local model.

If an OpenAI request falls back to Local, Jarvis reuses the same already-sanitised knowledge context; it does not grant additional access during fallback.

## Failure behaviour

Knowledge retrieval is best-effort. If the read-only Outline tools are unavailable, authentication fails, search fails, or no useful match is found, member chat continues without a knowledge context rather than inheriting the Operations agent.

For undocumented CamCore-specific facts, Jarvis should say that the available knowledge does not establish the answer instead of inventing a role or configuration.

## Production verification

After deploying a release containing this boundary, test Private chat with both Local and OpenAI using a documented question such as:

> What is Earth in CamCore?

Expected behaviour:

- the response uses the documented high-level role when Outline contains it;
- the provider remains the selected provider;
- no Operations mode is entered;
- no private address, private FQDN, credential or administrative memory is exposed;
- a normal non-CamCore writing/general-chat request does not trigger an Outline lookup.
