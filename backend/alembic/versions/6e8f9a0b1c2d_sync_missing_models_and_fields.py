"""sync_missing_models_and_fields

Revision ID: 6e8f9a0b1c2d
Revises: 5d99af77c0d1
Create Date: 2026-09-29 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e8f9a0b1c2d'
down_revision: Union[str, Sequence[str], None] = '5d99af77c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users: hospital_id
    op.add_column('users', sa.Column('hospital_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_users_hospital_id'), 'users', ['hospital_id'], unique=False)
    op.create_foreign_key('fk_users_hospital_id_hospitals', 'users', 'hospitals', ['hospital_id'], ['id'], ondelete='SET NULL')

    # 2. queues: queue_date
    op.add_column('queues', sa.Column('queue_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False))
    op.create_index(op.f('ix_queues_queue_date'), 'queues', ['queue_date'], unique=False)
    op.create_index('ix_queues_date', 'queues', ['queue_date'], unique=False)
    op.create_unique_constraint('uq_queue_session_date', 'queues', ['opd_session_id', 'queue_date'])

    # 3. queue_entries: appointment_date, booking_source, notes, arrived_at, origin_address
    #    Drop the old unique constraint that is superseded by the date-aware one
    op.drop_constraint('uq_queue_token_number', 'queue_entries', type_='unique')
    op.drop_index('ix_queue_entries_queue_token', table_name='queue_entries')
    op.add_column('queue_entries', sa.Column('appointment_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False))
    op.add_column('queue_entries', sa.Column('booking_source', sa.String(length=30), server_default='ONLINE', nullable=False))
    op.add_column('queue_entries', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('queue_entries', sa.Column('arrived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('queue_entries', sa.Column('origin_address', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_queue_entries_appointment_date'), 'queue_entries', ['appointment_date'], unique=False)
    op.create_index('ix_queue_entries_queue_date_token', 'queue_entries', ['queue_id', 'appointment_date', 'token_number'], unique=False)
    op.create_unique_constraint('uq_queue_date_token_number', 'queue_entries', ['queue_id', 'appointment_date', 'token_number'])

    # 4. arrival_plans travel mode fields
    op.add_column('arrival_plans', sa.Column('driving_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('driving_distance_meters', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('bike_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('bike_distance_meters', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('walking_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('walking_distance_meters', sa.Integer(), nullable=True))
    op.add_column('arrival_plans', sa.Column('selected_travel_mode', sa.String(length=30), server_default='DRIVE', nullable=False))

    # 5. doctor_availability table
    op.create_table(
        'doctor_availability',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('availability_date', sa.Date(), nullable=False),
        sa.Column('is_available', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_id', 'availability_date', name='uq_doctor_date_availability'),
    )
    op.create_index(op.f('ix_doctor_availability_id'), 'doctor_availability', ['id'], unique=False)
    op.create_index(op.f('ix_doctor_availability_doctor_id'), 'doctor_availability', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_doctor_availability_availability_date'), 'doctor_availability', ['availability_date'], unique=False)
    op.create_index('ix_doctor_avail_doc_date', 'doctor_availability', ['doctor_id', 'availability_date'], unique=False)

    # 6. otp_tokens table
    op.create_table(
        'otp_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('otp_code', sa.String(length=64), nullable=False),
        sa.Column('purpose', sa.String(length=50), server_default='LOGIN', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_otp_tokens_id'), 'otp_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_otp_tokens_recipient'), 'otp_tokens', ['recipient'], unique=False)
    op.create_index('ix_otp_tokens_recipient_verified', 'otp_tokens', ['recipient', 'is_verified'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_otp_tokens_recipient_verified', table_name='otp_tokens')
    op.drop_index(op.f('ix_otp_tokens_recipient'), table_name='otp_tokens')
    op.drop_index(op.f('ix_otp_tokens_id'), table_name='otp_tokens')
    op.drop_table('otp_tokens')

    op.drop_index('ix_doctor_avail_doc_date', table_name='doctor_availability')
    op.drop_index(op.f('ix_doctor_availability_availability_date'), table_name='doctor_availability')
    op.drop_index(op.f('ix_doctor_availability_doctor_id'), table_name='doctor_availability')
    op.drop_index(op.f('ix_doctor_availability_id'), table_name='doctor_availability')
    op.drop_table('doctor_availability')

    op.drop_column('arrival_plans', 'selected_travel_mode')
    op.drop_column('arrival_plans', 'walking_distance_meters')
    op.drop_column('arrival_plans', 'walking_duration_seconds')
    op.drop_column('arrival_plans', 'bike_distance_meters')
    op.drop_column('arrival_plans', 'bike_duration_seconds')
    op.drop_column('arrival_plans', 'driving_distance_meters')
    op.drop_column('arrival_plans', 'driving_duration_seconds')

    op.drop_constraint('uq_queue_date_token_number', 'queue_entries', type_='unique')
    op.drop_index('ix_queue_entries_queue_date_token', table_name='queue_entries')
    op.drop_index(op.f('ix_queue_entries_appointment_date'), table_name='queue_entries')
    op.drop_column('queue_entries', 'origin_address')
    op.drop_column('queue_entries', 'arrived_at')
    op.drop_column('queue_entries', 'notes')
    op.drop_column('queue_entries', 'booking_source')
    op.drop_column('queue_entries', 'appointment_date')
    # Restore old constraint that was dropped in upgrade
    op.create_index('ix_queue_entries_queue_token', 'queue_entries', ['queue_id', 'token_number'], unique=False)
    op.create_unique_constraint('uq_queue_token_number', 'queue_entries', ['queue_id', 'token_number'])

    op.drop_constraint('uq_queue_session_date', 'queues', type_='unique')
    op.drop_index('ix_queues_date', table_name='queues')
    op.drop_index(op.f('ix_queues_queue_date'), table_name='queues')
    op.drop_column('queues', 'queue_date')

    op.drop_constraint('fk_users_hospital_id_hospitals', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_hospital_id'), table_name='users')
    op.drop_column('users', 'hospital_id')
