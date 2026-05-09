# CI/CD Pipeline

The GitHub workflow is organized as a software-engineering quality gate. Each
stage answers a different question before code is considered releasable.

## Stages

| Stage | Purpose | Main commands |
| --- | --- | --- |
| Quality | Compile, lint, test, and measure coverage | `ruff`, `compileall`, `pytest --cov`, `npm run build` |
| Security | Check dependency and source-code risk | `pip-audit`, `npm audit`, CodeQL |
| Documentation | Build a browsable documentation site | `mkdocs build` |
| Package | Assemble deployable artifacts | backend wheel, frontend dist, docs, deployment manifest |
| Deploy Testing | Gate deployments from development branches | GitHub environment: `testing` |
| Deploy Production | Gate deployments from `main` | GitHub environment: `production` |

## Coverage Analysis

`pytest --cov=backend` produces three reports:

- terminal summary in the Actions log
- `coverage.xml` for tools that understand Cobertura-style coverage
- an HTML report in the `quality-reports` artifact

Coverage is currently reported but not threshold-gated. Add
`--cov-fail-under=<percent>` when the team agrees on a realistic baseline.

## Security Scan

The workflow uses three layers:

- `pip-audit` for Python dependency vulnerabilities.
- `npm audit --omit=dev` for production frontend dependency vulnerabilities.
- CodeQL for static source-code security analysis.

## Deployment

The deployment jobs are intentionally placeholders. They create real GitHub
environment gates and consume the release bundle, but do not assume a hosting
platform yet. When the team picks a target, replace the placeholder command with
the server, Docker, Pages, or cloud deployment command.

## Artifacts

Artifacts are the files produced by CI so the team can inspect or reuse them
after the run finishes. This workflow uploads test reports, coverage HTML,
security scan JSON, backend wheel files, frontend `dist`, the generated docs
site, and a final release bundle.

Recommended branch policy:

- feature branches and `dev-pydanticAI`: deploy to `testing`
- `main`: deploy to `production`
- configure required reviewers on the `production` environment before enabling a real deploy
