---
name: analyzing-impact
description: >
  Analyze the impact of a proposed feature, plan, or implementation change. Use when the
  user asks to "assess the impact", "what's the impact of this change", "impact analysis",
  "risk assessment", "what could go wrong", "evaluate this proposal", "blast radius",
  "what will this affect", "change impact", or "consequence analysis". Also triggers on
  "should we do this", "is this safe to ship", or "what are the risks".
metadata:
  version: "0.1.0"
---

# Impact Analysis

Evaluate the security, performance, operational, and business impact of a proposed feature, architectural change, or implementation plan.

## Workflow

1. **Understand the proposal** — Read the plan, feature description, code diff, or design doc the user provides. If the proposal is verbal, summarize it back and confirm understanding before proceeding.
2. **Map the affected surface** — Identify all systems, services, data stores, APIs, and user-facing behaviors that the change touches directly or indirectly.
3. **Analyze each impact dimension** — Evaluate the proposal across all dimensions below.
4. **Risk matrix** — Score each dimension and produce an overall risk assessment.
5. **Recommendations** — Provide concrete mitigations for identified risks.

## Impact Dimensions

### Security Impact
- Does this introduce new attack surface (new endpoints, new inputs, new data flows)?
- Does it change authentication or authorization behavior?
- Does it handle sensitive data differently?
- Does it introduce new dependencies with their own attack surface?
- Could it be exploited if partially deployed or rolled back?

### Performance Impact
- Expected load changes (new queries, API calls, compute)
- Memory and storage implications
- Latency impact on critical paths
- Scalability ceiling changes
- Cache invalidation or warming requirements

### Operational Impact
- Deployment complexity (migrations, feature flags, coordination)
- Monitoring and alerting requirements
- Rollback feasibility and procedure
- On-call impact (new failure modes, new runbooks needed)
- Infrastructure changes required

### Data Impact
- Schema changes (migrations, backward compatibility)
- Data volume changes
- Data retention and compliance implications
- Backup and recovery considerations
- Data consistency during rollout

### Business Impact
- User-facing behavior changes
- Backward compatibility with existing clients/integrations
- Feature flag and gradual rollout strategy
- Documentation and communication requirements
- Dependencies on other teams or services

### Maintainability Impact
- Code complexity changes
- New technical debt introduced
- Testing burden (new test types needed, coverage gaps)
- Onboarding impact (will new developers understand this?)
- Future flexibility (does this close off or open up future options?)

## Risk Matrix

Score each dimension:

| Dimension | Likelihood (1-5) | Severity (1-5) | Risk Score | Key Concern |
|-----------|------------------|-----------------|------------|-------------|
| Security | | | | |
| Performance | | | | |
| Operational | | | | |
| Data | | | | |
| Business | | | | |
| Maintainability | | | | |

**Risk Score** = Likelihood × Severity. Overall risk = highest individual score.

Risk levels: 1-5 Low, 6-12 Medium, 13-19 High, 20-25 Critical.

## Report Format

### Proposal Summary
2-3 sentences describing the change being evaluated.

### Affected Surface
List of systems, services, and components affected, with a brief note on how each is impacted.

### Impact Assessment
For each dimension, a paragraph covering findings, concerns, and mitigations.

### Risk Matrix
The scored table above.

### Recommended Mitigations
Numbered list of specific actions to reduce risk, ordered by priority:
1. **Before implementation**: Design changes, architectural adjustments
2. **During implementation**: Testing requirements, review checkpoints
3. **At deployment**: Rollout strategy, monitoring setup, rollback triggers
4. **After deployment**: Validation steps, performance monitoring windows

### Go / No-Go Recommendation
Clear recommendation: **Go**, **Go with mitigations**, or **No-Go**, with rationale.
