DEFAULT_EXTERNAL_MANDATE = """Autonomously assess the in-scope environment for exploitable paths that could lead to unauthorized access, privilege escalation, or sensitive data exposure. Focus on remote code execution, authentication weaknesses, default credentials, authentication and authorization bypasses, misconfigurations leading to compromise, exposed secrets, injection attacks, and privilege-escalation validation. The focus should be on exploitability of high to critical risks. Customers require demonstration and proof to engage remediation teams."""

# WebUI compatibility name: its unqualified default is the External mandate.
DEFAULT_MANDATE = DEFAULT_EXTERNAL_MANDATE

DEFAULT_CLOUD_MANDATE = """Autonomously assess the in-scope cloud environment for security misconfigurations, privilege escalation paths, and exposure risks. Focus on IAM privilege escalation, cross-account/cross-plane trust abuse, publicly exposed services, credential and secret management weaknesses, and network segmentation gaps. Prioritize findings that enable unauthorized access, lateral movement, or sensitive data exposure. Generate leads for investigation and file verified findings with evidence."""

DEFAULT_INTERNAL_MANDATE = """Autonomously assess the selected internal assets for exploitable paths that could lead to unauthorized access, privilege escalation, lateral movement, or sensitive data exposure. Route every target-network action through the assigned Aegis endpoint. Keep model orchestration and reporting in Guard."""

DEFAULT_WEBAPP_MANDATE = """Autonomously assess the selected web applications for exploitable authentication, authorization, and application-layer vulnerabilities. Focus on authentication bypass,
broken access control, IDOR, injection, exposed secrets, unsafe file handling, SSRF, and meaningful privilege escalation or sensitive-data exposure. Validate findings with clear evidence suitable for remediation."""

DEFAULT_LLM_MANDATE = """Autonomously assess selected LLM-backed web applications for exploitable AI and application security weaknesses. Focus on direct and indirect prompt injection, unauthorized tool execution, cross-user or cross-tenant data disclosure, retrieval isolation failures, system prompt or secret exposure, agentic workflow abuse, and sandbox escape. Validate findings with minimal, non-destructive evidence suitable for remediation."""

DEFAULT_HUNT_MANDATES = {
    'external': DEFAULT_EXTERNAL_MANDATE,
    'internal': DEFAULT_INTERNAL_MANDATE,
    'cloud': DEFAULT_CLOUD_MANDATE,
    'webapp': DEFAULT_WEBAPP_MANDATE,
    'llm': DEFAULT_LLM_MANDATE,
}


DEFAULT_GUARDRAILS = """Operate only within authorized scope. Do not perform denial-of-service, stress testing, brute force, password spraying, credential stuffing, phishing, social engineering, malware deployment, persistence, destructive actions, or bulk data exfiltration. Do not modify production data, change credentials, create accounts, alter configurations, restart services, disable security controls, clear logs, or evade monitoring. Use low-rate, low-concurrency testing. Stop or back off if testing causes errors, instability, lockout risk, throttling, or service degradation. If sensitive data is encountered, collect only minimal metadata or redacted evidence needed to prove exposure. When following redirects, stop before sending active probes, credentials, payloads, or exploit attempts to assets outside authorized scope. Passive observation of the redirect chain is permitted."""

DEFAULT_FINISH_CRITERIA = """End the hunt early if any of the following occur:

1. A material critical compromise path has been validated.
2. Three consecutive iterations produce no new high-confidence findings.
3. If the agent encounters signs of service instability, account lockout risk, rate limiting, or operational impact, move on to another target.
4. If further progress would require brute force, phishing, persistence, or destructive testing, move on to another target.
5. Additional validation would materially increase risk without improving confidence.
6. The allotted duration expires."""

DEFAULT_HUNT_DURATION_HOURS = 24
