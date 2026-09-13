# Security

Applicable to every packet. Review only security and trust-boundary defects:

- authentication, authorization, tenant isolation, ownership checks, and privilege transitions;
- SQL/command/template/LDAP/XPath injection, XSS/CSRF, path traversal, SSRF, and unsafe redirects;
- secrets or sensitive data in source, logs, errors, analytics, or outbound requests;
- unsafe parsing/deserialization and missing runtime validation at external boundaries;
- webhook signatures, replay protection, billing/payment abuse, and external-service trust;
- untrusted request, path, query, form, header, cookie, queue, persisted, environment, and API data flows.

Trace source → validation/normalization → authorization → persistence/rendering/outbound sink. Do not report generic
correctness or style issues. Cosmetic security wording is not a finding.
