# ENS Tools Enterprise Development Agent (ENS-DEV-AGENT)

A full-stack autonomous development agent that continuously improves ENS.tools for production## Roles-ready enterprise deployment.



The agent acts as multiple positions simultaneously:

1. **Lead Developer / Architect** - System design, code architecture, best practices
2. **UX/UI Designer** - User experience, accessibility, design systems
3. **QA Engineer** - Testing, quality assurance, error detection
4. **Security Engineer** - Vulnerability scanning, security hardening
5. **DevOps Engineer** - Deployment prep, CI/CD, performance optimization

## Pipeline Stages

The agent runs a complete enterprise development pipeline:

### Stage 1: REQUIREMENTS
- Analyze functional requirements
- Define non-functional requirements (performance, scalability)
- Identify security requirements
- Compliance requirements (GDPR, etc.)

### Stage 2: ARCHITECTURE
- Design system architecture
- Choose technology stack
- Define component patterns
- Plan data layer

### Stage 3: UX DESIGN
- Design user experience
- Plan component library
- Accessibility compliance
- Responsive design patterns

### Stage 4: IMPLEMENTATION
- Write production code
- Fix TypeScript errors
- Implement features
- Follow best practices

### Stage 5: TESTING
- Run unit tests
- Type checking
- Build verification
- Coverage analysis

### Stage 6: SECURITY
- Dependency vulnerability scanning
- Secrets detection
- CORS configuration
- Security headers

### Stage 7: PERFORMANCE
- Bundle size analysis
- Lazy loading verification
- Dependency optimization
- Caching strategies

### Stage 8: DEPLOYMENT
- Deployment checklist
- Environment configuration
- CI/CD setup
- Documentation

## Usage

```bash
# Run the development agent
python3 ~/.openclaw/workspace/agents/ens-improver/dev_agent.py
```

## Configuration

| Setting | Value |
|---------|-------|
| Workspace | /Users/acc/ens.tools |
| Model | minimax-portal/MiniMax-M2.5 |
| Max cycle time | 10 minutes |

## Files

- `dev_agent.py` - Main agent script
- `.dev_state.json` - State persistence
- `pipeline.json` - Pipeline tracking
- `issues.json` - Issue tracking
- `dev_notes.md` - Development notes

## Alerting

The agent sends alerts to webchat when:
- Build fails
- Tests fail
- Security vulnerabilities found
- Pipeline completes
- Errors occur
