# Documentation Index

This directory contains the project documentation, organized by category.

## Directory Structure

```text
docs/
├─ architecture/   System design and architecture
├─ development/    Development guides and refactoring notes
├─ features/       Feature-specific documentation
├─ final-report/   Final project report
├─ ci-cd.md        CI/CD pipeline documentation
├─ index.md        MkDocs homepage
├─ RAG_README.md   RAG system documentation
└─ README.md       This index
```

## Documentation By Category

### Architecture And Design

- [Technical Design](architecture/TECHNICAL_DESIGN.md) - Complete technical architecture overview
- [Design Document](architecture/design-26s-8.md) - Detailed design with UI mockups and visual specifications
- [Database Overview](architecture/DATABASE_CURRENT_OVERVIEW.md) - Current database schema and relationships
- [Project Proposal](architecture/proposal-26s-8.md) - Original project proposal and requirements
- [Final Report](final-report/final-report-26s-8.md) - Project final report and summary

### Features

- [Email Feature](features/EMAIL_FEATURE.md) - Email workflow, configuration, inbox reading, and approval-based sending
- [Quiz Feature](features/QUIZ_FEATURE.md) - Interactive quiz generation, grading, and practice history with expandable attempt detail
- [Blackboard Feature](features/BLACKBOARD_FEATURE.md) - SUSTech Blackboard integration, course listing, file browsing, and calendar sync
- [Memory System Implementation](features/MEMORY_SYSTEM_IMPLEMENTATION.md) - Intelligent memory, semantic search, context management, and tool learning
- [Web Search](features/WEB_SEARCH.md) - Search feature design and integration notes
- [Skills And MCP](features/SKILLS_MCP.md) - Local skill discovery, runtime MCP configuration, and encrypted MCP secrets
- [RAG System](RAG_README.md) - Local knowledge base setup and usage

### Development

- [Database Refactoring Summary](development/DATABASE_REFACTOR_SUMMARY.md) - Migration history and schema changes
- [Database Refactoring Summary (Chinese)](development/DATABASE_REFACTOR_SUMMARY_ZH.md) - Chinese version of the refactoring summary
- [CI/CD Pipeline](ci-cd.md) - GitHub workflow layout, testing strategies, and deployment gates
- [Documentation Site](index.md) - MkDocs entry point
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute to the project

## Quick Links

### Getting Started

- [Project README](../README.md)
- [Documentation Site](index.md)
- [Technical Design](architecture/TECHNICAL_DESIGN.md)
- [Design Document](architecture/design-26s-8.md)

### Feature-Focused Reading

- [Email Feature](features/EMAIL_FEATURE.md)
- [Quiz Feature](features/QUIZ_FEATURE.md)
- [Blackboard Feature](features/BLACKBOARD_FEATURE.md)
- [Memory System Implementation](features/MEMORY_SYSTEM_IMPLEMENTATION.md)
- [Web Search](features/WEB_SEARCH.md)
- [Skills And MCP](features/SKILLS_MCP.md)
- [RAG System](RAG_README.md)

### Development-Focused Reading

- [CI/CD Pipeline](ci-cd.md)
- [Database Refactoring Summary](development/DATABASE_REFACTOR_SUMMARY.md)
- [Contributing Guide](../CONTRIBUTING.md)

## Document Conventions

- Architecture documents explain system structure, components, and design decisions.
- Feature documents focus on what a feature does, how it behaves, and how it is used.
- Development documents cover engineering process, migration history, and implementation notes.

## Notes

- Start with [Technical Design](architecture/TECHNICAL_DESIGN.md) if you want the broadest system overview.
- Use the `features/` directory when you want to understand a capability end to end.
- Use your editor search across `docs/` when looking for a specific subsystem or workflow.
