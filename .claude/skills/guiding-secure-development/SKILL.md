---
name: guiding-secure-development
description: >
  Reference guide for secure coding patterns and vulnerability remediation. Use when
  the user asks "how do I fix this vulnerability", "secure coding best practices",
  "how to prevent XSS", "how to prevent SQL injection", "security hardening",
  "secure this code", "what's the secure way to do this", "fix this security issue",
  or needs guidance on writing secure code. Also triggers on "OWASP remediation",
  "CWE fix", or "security best practice for".
metadata:
  version: "0.1.0"
---

# Secure Development Guide

Provide actionable secure coding guidance, vulnerability remediation patterns, and hardening checklists.

## When to Use

This skill is a reference companion to the security-audit skill. Use it when:

- A security audit has identified vulnerabilities and the user needs help fixing them
- The user is writing new code and wants to follow secure patterns from the start
- The user asks how to prevent a specific vulnerability class
- The user needs a hardening checklist for a specific technology

## Guidance Process

1. **Identify the context** — What language, framework, and vulnerability class?
2. **Provide the secure pattern** — Show the correct way to write the code, with a brief explanation of why it's secure.
3. **Show the insecure pattern** — Show the vulnerable version so the user can recognize it in existing code.
4. **Explain the attack** — Brief description of how the vulnerability is exploited.
5. **Link to standards** — Reference the relevant OWASP or CWE entry.

## Core Vulnerability Classes

### Injection (CWE-89, CWE-78, CWE-917)
- SQL injection: Use parameterized queries, never string concatenation
- Command injection: Avoid shell=True, use argument arrays, validate inputs
- Expression injection: Sanitize template inputs, avoid eval-like constructs

### Cross-Site Scripting / XSS (CWE-79)
- Use framework auto-escaping (React JSX, Django templates)
- Never use innerHTML or dangerouslySetInnerHTML with user input
- Implement Content-Security-Policy headers
- Sanitize HTML with allowlisted tags when rich text is required

### Broken Authentication (CWE-287)
- Use established auth libraries, never roll your own
- Enforce strong password policies with bcrypt/scrypt/argon2 hashing
- Implement rate limiting on auth endpoints
- Use secure session management with HttpOnly, Secure, SameSite cookies

### Sensitive Data Exposure (CWE-200)
- Encrypt data at rest and in transit (TLS 1.2+)
- Never log sensitive data (tokens, passwords, PII)
- Mask sensitive fields in API responses
- Use environment variables or secret managers for credentials

### Broken Access Control (CWE-284)
- Implement authorization checks at every endpoint
- Use deny-by-default, not allow-by-default
- Validate object-level access (IDOR prevention)
- Apply principle of least privilege

### Security Misconfiguration (CWE-16)
- Disable debug mode and verbose errors in production
- Remove default credentials and unnecessary features
- Set appropriate CORS, CSP, and other security headers
- Keep frameworks and dependencies updated

### Insecure Deserialization (CWE-502)
- Never deserialize untrusted data with native serializers (pickle, Java ObjectInputStream)
- Use JSON or other data-only formats
- Validate and sanitize before deserialization
- Implement integrity checks (HMAC) on serialized objects

## Hardening Checklists

When the user asks for a hardening checklist, consult `references/hardening-checklists.md` for technology-specific lists covering:

- Web application hardening
- API security hardening
- Container and Kubernetes hardening
- CI/CD pipeline security
- Database hardening
- Cloud infrastructure (AWS/GCP/Azure) basics

## Output Style

When providing remediation guidance:

1. Lead with the **fix** — show working, secure code first
2. Keep explanations concise — developers need to ship
3. Always include a **before/after** code comparison
4. Reference the specific CWE or OWASP category
5. Note any trade-offs (performance, complexity) of the secure approach

## Additional Resources

- **`references/hardening-checklists.md`** — Technology-specific hardening checklists
