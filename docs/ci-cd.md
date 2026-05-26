# CI/CD Pipeline

This project implements a fully automated CI/CD system using **GitHub Actions**, covering build, test, security scanning, code metrics, documentation, packaging, containerization, and deployment preparation.

## Workflow Overview

Two workflows drive the pipeline:

| Workflow | File | Purpose |
| --- | --- | --- |
| CI/CD | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Build, test, scan, package, and deploy gate |
| Docker Build & Release | [`.github/workflows/docker-release.yml`](../.github/workflows/docker-release.yml) | Container image build and GitHub Release publishing |

---

## CI/CD Workflow

### Trigger Conditions

| Event | Branches |
| --- | --- |
| Push | `main`, `dev-pydanticAI`, `feature/**`, `codex/**` |
| Pull Request | `main`, `dev-pydanticAI` |
| Manual | `workflow_dispatch` |

### Jobs

#### 1. Quality (`quality`)

Front-to-back validation of code correctness and buildability.

- **Setup**: Python 3.11 (with `uv`), Node.js 20 (with `npm`)
- **Ruff**: lint and format check on `backend` and `tests`
- **Compile check**: `compileall` on `backend` and `tests`
- **Pytest**: coverage collection via `pytest-cov`, producing:
  - JUnit XML (`pytest.xml`)
  - Cobertura XML (`coverage.xml`)
  - HTML coverage report
- **Backend wheel**: built with `uv build --wheel`
- **Frontend build**: `npm ci` + `npm run build`, output collected to `artifacts/frontend-dist`
- **Artifacts**: `quality-reports` (test + coverage) and `build-outputs` (backend wheel + frontend dist), retained 14 days

#### 2. Code Metrics (`code-analysis`)

Automated repository analysis generating an HTML dashboard.

- **cloc**: counts lines of code, files, comments, and blanks per language
- **lizard**: cyclomatic complexity analysis with CCN threshold of 15
- **Dependency extraction**: runtime and dev dependencies parsed from `pyproject.toml` and `frontend/package.json`
- **HTML dashboard**: self-contained `report.html` with interactive tabs for LOC, complexity, and dependency overview
- **Artifact**: `code-metrics`, retained 14 days

#### 3. Security (`security`)

Dependency vulnerability scanning for both ecosystems.

- **pip-audit**: scans Python dependencies, outputs JSON to `artifacts/security/pip-audit.json`
- **npm audit**: scans production frontend dependencies (`--audit-level=high --omit=dev`), outputs JSON to `artifacts/security/npm-audit.json`
- Both steps use `continue-on-error: true` to avoid blocking the pipeline on advisory noise
- **Artifact**: `security-reports`, retained 14 days

#### 4. CodeQL (`codeql`)

Static source-code security analysis for Python and JavaScript/TypeScript.

- **Conditional**: only runs when the repository variable `ENABLE_CODEQL` is set to `true`
- Uses `build-mode: none` (no compilation step needed)
- Results uploaded to GitHub Security tab

#### 5. Documentation (`docs`)

- Builds static documentation site with **MkDocs** (`mkdocs build`)
- **Artifact**: `docs-site`, retained 14 days

#### 6. Package (`package`)

Assembles the final release bundle. Depends on `quality`, `security`, `code-analysis`, and `docs`.

- Downloads all upstream artifacts (build outputs, docs site, code metrics)
- Generates a `deployment-manifest.json` with repository metadata and contents list
- **Artifact**: `release-bundle`, retained 30 days

#### 7. Deploy Testing (`deploy-testing`)

GitHub environment gate for non-production branches. Triggers on push to `dev-pydanticAI`, `feature/**`, or `codex/**`.

- Environment: `testing`
- Currently a **placeholder** — downloads the release bundle and prints the manifest
- Replace with the actual testing deployment command when a hosting target is chosen

#### 8. Deploy Production (`deploy-production`)

GitHub environment gate for the `main` branch.

- Environment: `production`
- Currently a **placeholder** — downloads the release bundle and prints the manifest
- **Configure required reviewers** on the `production` environment before enabling a real deploy

### Job Dependency Graph

```
quality ──┬────────────────────┐
          │                    │
code-analysis                  │
          │                    │
security ─┤                    │
          │                    │
  docs ───┘                    │
          │                    │
       package ────────────────┤
          │                    │
    deploy-testing    deploy-production
```

---

## Docker Build & Release Workflow

A separate workflow handles containerization and release publishing.

### Trigger Conditions

| Event | Condition |
| --- | --- |
| Push to branch | `main`, `feature/docker-release` |
| Push tag | `v*` |
| Manual | `workflow_dispatch` |

### Jobs

#### Build & Push Backend (`build-backend`)

- Uses `docker/build-push-action@v7` with Buildx
- Context: repository root; Dockerfile: `./backend/Dockerfile`
- Publishes to **GitHub Container Registry** (`ghcr.io`)
- Tagging strategy:
  - `v*` tags → semantic version tag (e.g. `v1.0.0`)
  - `main` branch → `latest`
  - Other branches → commit SHA
- Always also tagged with the full commit SHA for traceability
- Uses GHA cache (`type=gha`) for layer caching

#### Build & Push Frontend (`build-frontend`)

- Context: `./frontend`; Dockerfile: `./frontend/Dockerfile`
- Same registry and tagging strategy as backend

#### GitHub Release (`release`)

- Only runs on `v*` tag pushes (depends on both build jobs)
- Generates:
  - `docker-compose.yml` referencing the tagged images with health checks and volume mounts
  - `README.txt` with quick-start and air-gapped deployment instructions
- Creates a GitHub Release via `softprops/action-gh-release@v3` with auto-generated release notes

### Container Images

| Image | Registry Path | Health Check |
| --- | --- | --- |
| Backend | `ghcr.io/sustech-cs304/team-project-26spring-26s-8/backend` | `GET /api/health` (30s interval) |
| Frontend | `ghcr.io/sustech-cs304/team-project-26spring-26s-8/frontend` | — |

---

## Tools and Technologies

| Stage | Tools |
| --- | --- |
| CI/CD Orchestration | GitHub Actions |
| Backend | Python 3.11, uv, Pytest |
| Frontend | Vue.js, Node.js 20, npm |
| Code Quality | Ruff (lint + format) |
| Metrics | cloc, lizard |
| Security | pip-audit, npm audit, CodeQL |
| Documentation | MkDocs |
| Containerization | Docker, Buildx |
| Registry | GitHub Container Registry (GHCR) |

---

## Recommended Branch Policy

- Feature branches and `dev-pydanticAI`: deploy to `testing` environment
- `main`: deploy to `production` environment
- Configure required reviewers on the `production` environment before enabling a real deploy
- CodeQL is opt-in via the `ENABLE_CODEQL` repository variable
