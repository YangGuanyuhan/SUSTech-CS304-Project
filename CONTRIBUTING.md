# Contributing Guide
## 1. Development Workflow

We follow a simplified Git workflow:

- main: stable release version
- dev-pydanticAI: integration branch
- feature/*: new features
- bugfix/*: bug fixes

## 2. Commit Message Convention
Use clear and structured commit messages:
```
feat: add quiz generation agent 
fix: resolve async database issue
refactor: simplify service layer
test: add unit tests for agent
chore: update dependencies / config
docs: update README or contributing guide
```


## 3. Collaboration Rules
- Do not push directly to `main`
- Prefer working on `feature/*` or `bugfix/*` branches
- Small bug fixes can be committed directly to `dev-pydanticAI`
- **Make commits small and focused — each commit should cover a single logical change**
- Ensure code runs before pushing
- Avoid breaking existing functionality
- **Before starting new work, merge the latest dev-pydanticAI into your branch**
- **After finishing your work, if dev-pydanticAI has been updated in the meantime, merge it again before pushing your commits**

## 4. Notes
- Do not commit `.env` files or other sensitive information
- Write clear, maintainable, and well-commented code
- Consider opening a Pull Request for larger changes for easier review