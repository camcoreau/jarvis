# Member knowledge production verification

After the immutable image for this change is deployed, verify the signed-in `camcore.au/jarvis` **Private chat** route with both OpenAI and Local providers.

Primary test:

> What is Earth in CamCore?

The answer should use the documented high-level role from Outline when a relevant document exists. It must not show an IP address, private `camcore.network` FQDN, credential, admin-only procedure, or live-state claim.

Then send a general prompt that is unrelated to CamCore, for example:

> Rewrite this sentence to be clearer.

That request should remain normal member chat and should not require a CamCore knowledge lookup.

Finally confirm Operations mode is unchanged for an administrator and the provider selector still reports the actual provider/model used.
