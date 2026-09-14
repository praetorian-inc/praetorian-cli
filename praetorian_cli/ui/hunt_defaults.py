DEFAULT_GUARDRAILS = """Operate only within authorized scope. Do not perform denial-of-service, stress testing, brute force, password spraying, credential stuffing, phishing, social engineering, malware deployment, persistence, destructive actions, or bulk data exfiltration. Do not modify production data, change credentials, create accounts, alter configurations, restart services, disable security controls, clear logs, or evade monitoring. Use low-rate, low-concurrency testing. Stop or back off if testing causes errors, instability, lockout risk, throttling, or service degradation. If sensitive data is encountered, collect only minimal metadata or redacted evidence needed to prove exposure. When following redirects, stop before sending active probes, credentials, payloads, or exploit attempts to assets outside authorized scope. Passive observation of the redirect chain is permitted."""

DEFAULT_FINISH_CRITERIA = """End the hunt early if any of the following occur:

1. A material critical compromise path has been validated.
2. Three consecutive iterations produce no new high-confidence findings.
3. If the agent encounters signs of service instability, account lockout risk, rate limiting, or operational impact, move on to another target.
4. If further progress would require brute force, phishing, persistence, or destructive testing, move on to another target.
5. Additional validation would materially increase risk without improving confidence.
6. The allotted duration expires."""

DEFAULT_HUNT_DURATION_HOURS = 24
