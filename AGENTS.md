# Project Instructions

## Execute Security Scanners

### Execute SCA Scanner When:

- New dependencies are added to the project
- Dependencies are updated to new versions
- Lock files are modified (e.g.,`package-lock.json`, `uv.lock`)
- User explicitly requests a dependency security scan
- Setting up a new project for the first time
- Before deploying to production
- Before pushing to the repository

### Execute SAST Scanner When:

- Source code changes are made to application files
- New features or modules are added
- Security-sensitive code is modified (authentication, authorization)
- User explicitly requests a code security scan
- Before committing significant code changes
- During code reviews
- Before deploying to production
- Before pushing to the repository

### Execute Both Scanners When:

- Complete security audit is needed
- Major project updates involving both code and dependencies
- Pre-deployment security check
- User requests a full security scan

## Prerequisites

- Docker installed on the system
- No Dockerfile creation needed - only download the Docker images
- Write access to the project directory for configuration files and results

## Fluid Attacks Scanner

### Purpose

Scan the project for vulnerabilities using the Fluid Attacks MCP tools.

### Step-by-Step Instructions

#### 1. Use Fluid Attack MCP tools to configure and run the scanner

#### 2. Add the output file to .gitignore

#### 3. Remediate vulnerabilities

- Review the output file
- If there are vulnerabilities, remediate them

## Best Practices for Agents

### 1. Configuration File Management

- Always verify the correct paths for include/exclude before running
- Adjust configuration based on project structure
- Use `.gitignore` as a reference for exclude patterns
- Store configuration files in the project root and add them to .gitignore
- Add the output file (Fluid-Attacks-Results.csv) to .gitignore

## When to Run What

| Scenario                      | Scanner | Priority |
| ----------------------------- | ------- | -------- |
| New dependency added          | SCA     | High     |
| Code changes in auth/security | SAST    | Critical |
| Weekly security audit         | Both    | Medium   |
| Pre-deployment check          | Both    | Critical |
| Dependency version update     | SCA     | High     |
| New feature development       | SAST    | Medium   |
| Third-party library added     | SCA     | High     |
| API endpoint changes          | SAST    | High     |

## Integration with Development Workflow

- On Code Changes: Run SAST if source files modified
- On Dependency Changes: Run SCA if dependency files modified
- On User Request: Run appropriate scanner(s)
- Help with remediation: Always create/update security reports
- Re-scan: After fixes to verify remediation
