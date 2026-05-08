# Documentation Index

This directory contains all project documentation organized by category.

## 📁 Directory Structure

```
docs/
├── architecture/     # System design and architecture
├── development/      # Development guides and processes
├── features/         # Feature-specific documentation
└── RAG_README.md    # RAG system documentation
```

## 📚 Documentation by Category

### Architecture & Design

**System Architecture**
- [Technical Design](architecture/TECHNICAL_DESIGN.md) - Complete technical architecture overview
- [Design Document](architecture/design-26s-8.md) - Detailed design with UI mockups and visual specifications
- [Database Overview](architecture/DATABASE_CURRENT_OVERVIEW.md) - Current database schema and relationships

**Project Planning**
- [Project Proposal](architecture/proposal-26s-8.md) - Original project proposal and requirements

### Features

**Memory System** ⭐ NEW
- [Memory System Implementation](features/MEMORY_SYSTEM_IMPLEMENTATION.md)
  - Comprehensive memory system with semantic search
  - Token-aware context management
  - Tool learning and pattern recognition
  - Memory lifecycle management
  - 24 tests, all passing

**RAG & Knowledge Base**
- [RAG System](RAG_README.md) - Local knowledge base setup and usage

### Development

**Database**
- [Database Refactoring Summary](development/DATABASE_REFACTOR_SUMMARY.md) - Migration history and changes
- [Database Refactoring Summary (中文)](development/DATABASE_REFACTOR_SUMMARY_ZH.md) - 中文版本

**Contributing**
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute to the project

## 🔍 Quick Links by Topic

### Getting Started
- Start here: [README](../README.md)
- Architecture overview: [Technical Design](architecture/TECHNICAL_DESIGN.md)
- UI/UX design: [Design Document](architecture/design-26s-8.md)

### Implementation Details
- Memory system: [Memory Implementation](features/MEMORY_SYSTEM_IMPLEMENTATION.md)
- Database schema: [Database Overview](architecture/DATABASE_CURRENT_OVERVIEW.md)
- RAG setup: [RAG README](RAG_README.md)

### Development
- Contributing: [Contributing Guide](../CONTRIBUTING.md)
- Database changes: [Refactoring Summary](development/DATABASE_REFACTOR_SUMMARY.md)

## 📝 Document Conventions

- **Architecture docs**: High-level system design, component interactions, architectural decisions
- **Feature docs**: Detailed implementation of specific features, including code examples and usage
- **Development docs**: Process documentation, migration guides, refactoring notes

## 🆕 Recent Updates

- **2024-05**: Memory System Enhancement - Added comprehensive memory system with semantic search, context management, and tool learning
- **2024-04**: Database Refactoring - Migrated to improved schema with better relationships
- **2024-03**: Initial Architecture - Established core system design

## 💡 Tips

- Use the search function in your editor to find specific topics across all docs
- Check the [Technical Design](architecture/TECHNICAL_DESIGN.md) first for understanding the overall system
- Feature-specific questions? Look in the `features/` directory
- Implementation details are in the actual code with inline comments
