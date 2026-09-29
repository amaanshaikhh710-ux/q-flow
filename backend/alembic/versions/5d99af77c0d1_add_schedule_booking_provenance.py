"""retain schedule and selected time on queue appointments

Revision ID: 5d99af77c0d1
Revises: 4f88e1a7b29c
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "5d99af77c0d1"
down_revision: Union[str, Sequence[str], None] = "4f88e1a7b29c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("queue_entries", sa.Column("schedule_id", sa.Uuid(), nullable=True))
    op.add_column("queue_entries", sa.Column("appointment_time", sa.Time(), nullable=True))
    op.create_index("ix_queue_entries_schedule_id", "queue_entries", ["schedule_id"])
    op.create_foreign_key(
        "fk_queue_entries_schedule_id", "queue_entries", "doctor_schedules",
        ["schedule_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_queue_entries_schedule_id", "queue_entries", type_="foreignkey")
    op.drop_index("ix_queue_entries_schedule_id", table_name="queue_entries")
    op.drop_column("queue_entries", "appointment_time")
    op.drop_column("queue_entries", "schedule_id")
