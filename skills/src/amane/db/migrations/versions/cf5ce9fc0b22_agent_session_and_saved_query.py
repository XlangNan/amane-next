"""agent session and saved query

Revision ID: cf5ce9fc0b22
Revises: 53476adaa9cd
Create Date: 2026-08-09 13:43:00.412668
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf5ce9fc0b22"
down_revision: str | None = "53476adaa9cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_sessions_status"), "agent_sessions", ["status"], unique=False)
    op.create_table(
        "saved_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sql", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("persisted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_queries_entity"), "saved_queries", ["entity"], unique=False)
    op.create_index(op.f("ix_saved_queries_persisted"), "saved_queries", ["persisted"], unique=False)
    op.create_index(op.f("ix_saved_queries_session_id"), "saved_queries", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_queries_session_id"), table_name="saved_queries")
    op.drop_index(op.f("ix_saved_queries_persisted"), table_name="saved_queries")
    op.drop_index(op.f("ix_saved_queries_entity"), table_name="saved_queries")
    op.drop_table("saved_queries")
    op.drop_index(op.f("ix_agent_sessions_status"), table_name="agent_sessions")
    op.drop_table("agent_sessions")
