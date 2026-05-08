"""Migration script to add enhanced memory tables.

This migration adds:
1. long_term_memories table with semantic search support
2. tool_usage_patterns table for learning tool usage
3. token_count and importance_score columns to task_history
"""

from sqlalchemy import text


def upgrade(connection):
    """Apply migration."""
    # Check if columns already exist before adding
    result = connection.execute(text("PRAGMA table_info(task_history)"))
    existing_columns = {row[1] for row in result}

    # Add columns to task_history (SQLite requires separate ALTER TABLE for each column)
    if "token_count" not in existing_columns:
        connection.execute(
            text("ALTER TABLE task_history ADD COLUMN token_count INTEGER DEFAULT 0")
        )
    if "importance_score" not in existing_columns:
        connection.execute(
            text("ALTER TABLE task_history ADD COLUMN importance_score REAL DEFAULT 1.0")
        )

    # Check if long_term_memories table exists
    result = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='long_term_memories'")
    )
    if result.fetchone() is None:
        # Create long_term_memories table
        connection.execute(
            text(
                """
            CREATE TABLE long_term_memories (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL DEFAULT 'local-user',
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                meta_data TEXT NOT NULL DEFAULT '{}',
                source_session_id TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP WITH TIME ZONE NOT NULL,
                importance_score REAL DEFAULT 1.0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
            """
            )
        )

        # Create indexes for long_term_memories
        connection.execute(
            text(
                """
            CREATE INDEX ix_ltm_owner_type_created
            ON long_term_memories(owner_id, memory_type, created_at)
            """
            )
        )
        connection.execute(
            text(
                """
            CREATE INDEX ix_ltm_owner_importance
            ON long_term_memories(owner_id, importance_score)
            """
            )
        )
        connection.execute(
            text("CREATE INDEX ix_ltm_session ON long_term_memories(source_session_id)")
        )

    # Check if tool_usage_patterns table exists
    result = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='tool_usage_patterns'")
    )
    if result.fetchone() is None:
        # Create tool_usage_patterns table
        connection.execute(
            text(
                """
            CREATE TABLE tool_usage_patterns (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL DEFAULT 'local-user',
                tool_name TEXT NOT NULL,
                user_query TEXT NOT NULL,
                tool_arguments TEXT NOT NULL,
                outcome TEXT NOT NULL,
                success BOOLEAN DEFAULT TRUE,
                confidence_score REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
            """
            )
        )

        # Create indexes for tool_usage_patterns
        connection.execute(
            text(
                """
            CREATE INDEX ix_tool_patterns_tool_confidence
            ON tool_usage_patterns(tool_name, confidence_score)
            """
            )
        )
        connection.execute(
            text(
                """
            CREATE INDEX ix_tool_patterns_owner_created
            ON tool_usage_patterns(owner_id, created_at)
            """
            )
        )

    connection.commit()


def downgrade(connection):
    """Revert migration."""
    # Drop new tables
    connection.execute(text("DROP TABLE IF EXISTS tool_usage_patterns"))
    connection.execute(text("DROP TABLE IF EXISTS long_term_memories"))

    # Note: SQLite doesn't support DROP COLUMN, so we can't easily remove
    # the columns from task_history. In production, you'd need to:
    # 1. Create new table without those columns
    # 2. Copy data
    # 3. Drop old table
    # 4. Rename new table
    # For now, we'll leave them (they won't hurt)

    connection.commit()


if __name__ == "__main__":
    from backend.db.database import engine

    with engine.connect() as conn:
        print("Running migration...")
        upgrade(conn)
        print("Migration completed successfully!")
