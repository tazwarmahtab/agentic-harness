# Restricted document pilot entry
6 November 2026. Implementation candidate 2374f9676bac54b26297b3a555ec509942b2a3af; not independently reviewed or released.

Adds aos/pilot.py: separate FastAPI entry, existing authenticated document router and body limit only, no legacy API mount and no public schema/docs endpoints. Run with .venv/bin/uvicorn aos.pilot:app --host 127.0.0.1 --port 7001 after configuring AOS_API_TOKEN privately. Existing prospect model-disclosure gating remains unchanged; this slice does not redesign document behavior or grant provider authorization.

Seven new tests first failed because the entry was missing. Following implementation, one test relied on FastAPI internal route structure; it was corrected to use the public schema. Final scoped suite: 37 passed, one existing Starlette/httpx deprecation warning, 3.70 seconds. Focused Ruff lint and format pass. Named legacy paths reject GET and POST; document reads require configured valid token. New files fetched at saved head match tested local contents.

No full-suite execution: legacy destructive-denial safety repair remains pending. No independent review, browser/product-design audit, submodule initialization, CI, generic wording, approved export, live worker, public deployment or release completion claimed. Source snapshot before these additive changes: 63a378ad9c387dbe277cafd24817286994e24117. All archived contributions retained.

Next: verify actual loopback server startup and UI handoff; capture existing flow before Product Design findings; implement generic document mode and exact approved export with adversarial tests. Application route isolation is not OS sandboxing or proof of complete authorization safety.
