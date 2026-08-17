# qualification-live

Provider-native OpenAI, Anthropic, and Google Gemini adapters plus controlled M2.6 tournament
orchestration. This package accepts only synthetic qualification requests, exposes no provider SDK
types, persists no raw payloads or secrets, and is not imported by application services or normal CI.

Live execution occurs only through `scripts/run_m26_tournament.py` with explicit flags, allowlists,
kill switch, credential file, and a fail-closed USD 50 budget.
