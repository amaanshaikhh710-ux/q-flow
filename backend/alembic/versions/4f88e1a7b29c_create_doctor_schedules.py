"""create doctor_schedules table

Revision ID: 4f88e1a7b29c
Revises: 347d1479409f
Create Date: 2026-09-20 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f88e1a7b29c'
down_revision: Union[str, Sequence[str], None] = '347d1479409f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="AVAILABLE", nullable=False),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=True),
        sa.Column("opd_session_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opd_session_id"], ["opd_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "schedule_date", name="uq_doctor_schedule_date"),
    )
    op.create_index(op.f("ix_doctor_schedules_id"), "doctor_schedules", ["id"], unique=False)
    op.create_index(op.f("ix_doctor_schedules_hospital_id"), "doctor_schedules", ["hospital_id"], unique=False)
    op.create_index(op.f("ix_doctor_schedules_doctor_id"), "doctor_schedules", ["doctor_id"], unique=False)
    op.create_index(op.f("ix_doctor_schedules_department_id"), "doctor_schedules", ["department_id"], unique=False)
    op.create_index(op.f("ix_doctor_schedules_schedule_date"), "doctor_schedules", ["schedule_date"], unique=False)
    op.create_index("ix_doctor_schedules_hosp_date", "doctor_schedules", ["hospital_id", "schedule_date"], unique=False)
    op.create_index("ix_doctor_schedules_doc_date", "doctor_schedules", ["doctor_id", "schedule_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_doctor_schedules_doc_date", table_name="doctor_schedules")
    op.drop_index("ix_doctor_schedules_hosp_date", table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_schedule_date"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_department_id"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_doctor_id"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_hospital_id"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_id"), table_name="doctor_schedules")
    op.drop_table("doctor_schedules")
