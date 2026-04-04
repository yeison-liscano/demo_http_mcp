# Hardening Checklists

Technology-specific security hardening guides. Use these when the user asks for a hardening review of a specific technology stack.

## Web Application Hardening

### HTTP Security Headers
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` — Enforce HTTPS
- `Content-Security-Policy: default-src 'self'` — Prevent XSS and injection (customize per app)
- `X-Content-Type-Options: nosniff` — Prevent MIME sniffing
- `X-Frame-Options: DENY` or `SAMEORIGIN` — Prevent clickjacking
- `Referrer-Policy: strict-origin-when-cross-origin` — Limit referrer leakage
- `Permissions-Policy: camera=(), microphone=(), geolocation=()` — Disable unnecessary browser APIs

### Session Management
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict`)
- Session timeout: 15-30 minutes idle, 8-12 hours absolute
- Session ID rotation after login
- Session invalidation on logout (server-side)
- Session storage server-side (not just JWT)

### Input Handling
- Validate on server side (never trust client validation alone)
- Whitelist validation where possible (allowed characters, formats)
- Maximum input lengths enforced
- File uploads: type validation, size limits, virus scanning, isolated storage
- Content-Type enforcement on API endpoints

## API Security Hardening

### Authentication
- Use OAuth 2.0 / OpenID Connect for third-party auth
- API keys: rotate regularly, scope to specific operations, transmit in headers (not URLs)
- JWT: short expiration (15 min), use refresh tokens, validate all claims
- No credentials in query parameters or logs

### Rate Limiting
- Global rate limit per IP
- Per-user rate limit on authenticated endpoints
- Stricter limits on auth endpoints (login, password reset, registration)
- Rate limit headers returned: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`

### Request Validation
- Maximum request body size enforced
- Content-Type validation
- Schema validation on all inputs (JSON Schema, Zod, etc.)
- Reject unknown fields in strict mode
- Pagination limits enforced (max page size)

### Response Security
- No internal IDs, stack traces, or server versions in responses
- Field-level filtering (don't serialize entire DB objects)
- Consistent error format (no information leakage in error details)
- CORS restricted to specific origins

## Container & Kubernetes Hardening

### Container Images
- Use minimal base images (distroless, Alpine)
- Run as non-root user (`USER nonroot` in Dockerfile)
- No secrets in images or build args
- Pin base image digests (not just tags)
- Scan images for vulnerabilities before deployment
- Multi-stage builds to exclude build tools from runtime

### Kubernetes Security
- Pod Security Standards: `restricted` baseline
- Network policies: deny all ingress/egress by default, allow explicitly
- Resource limits (CPU, memory) on all containers
- Read-only root filesystem where possible
- Service accounts: don't use default, minimize RBAC permissions
- Secrets: use external secret managers, not K8s secrets for sensitive data
- Disable automountServiceAccountToken when not needed

## CI/CD Pipeline Security

### Source Control
- Branch protection on main/production branches
- Signed commits for release branches
- No secrets in repository (use secret scanning)
- Dependency scanning in CI
- License compliance checks

### Build Pipeline
- Reproducible builds
- SBOM generation
- Artifact signing
- Separate build and deploy credentials
- Pipeline-as-code (versioned, reviewed)
- No `sudo` or privileged operations in build steps

### Deployment
- Infrastructure as code (versioned, reviewed)
- Immutable deployments (no in-place modifications)
- Automated rollback on health check failure
- Deployment auditing (who deployed what, when)
- Environment separation (dev/staging/production credentials isolated)

## Database Hardening

### Access Control
- Principle of least privilege for database users
- Application uses a dedicated DB user (not root/admin)
- Separate read and write users where possible
- Network-level access restrictions (VPC, security groups)
- No remote root access

### Data Protection
- Encryption at rest enabled
- TLS for all database connections
- Sensitive fields encrypted at application level
- Regular backup verification
- Point-in-time recovery configured
- Audit logging enabled for data access

### Query Security
- Parameterized queries only (no string concatenation)
- Query timeout limits
- Connection pooling with max limits
- Prepared statement caching
- No `SELECT *` in production code
