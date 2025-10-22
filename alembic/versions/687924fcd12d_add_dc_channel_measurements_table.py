"""Add DC channel measurements table

Revision ID: 687924fcd12d
Revises: a0d10f46b03b
Create Date: 2025-10-22 09:58:04.258398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '687924fcd12d'
down_revision: Union[str, None] = 'a0d10f46b03b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Create DC channel measurements table
    op.create_table(
        'dc_channel_measurements',
        sa.Column('time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('inverter_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('power', sa.Float(), nullable=False),
        sa.Column('voltage', sa.Float(), nullable=False),
        sa.Column('current', sa.Float(), nullable=False),
        sa.Column('yield_day_wh', sa.Float(), nullable=False),
        sa.Column('yield_total_kwh', sa.Float(), nullable=False),
        sa.Column('irradiation', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inverter_id'], ['inverter.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('time', 'user_id', 'inverter_id', 'channel'),
    )

    # Step 2: Convert to TimescaleDB hypertable with multi-dimensional partitioning
    op.execute("""
        SELECT create_hypertable(
            'dc_channel_measurements',
            'time',
            partitioning_column => 'user_id',
            number_partitions => 4,
            chunk_time_interval => INTERVAL '7 days'
        );
    """)

    # Step 3: Create indexes for performance
    op.execute("""
        CREATE INDEX idx_dc_user_time ON dc_channel_measurements (user_id, time DESC);
    """)
    op.execute("""
        CREATE INDEX idx_dc_inverter_time ON dc_channel_measurements (inverter_id, time DESC);
    """)
    op.execute("""
        CREATE INDEX idx_dc_channel ON dc_channel_measurements (inverter_id, channel, time DESC);
    """)

    # Step 4: Enable Row-Level Security
    op.execute("""
        ALTER TABLE dc_channel_measurements ENABLE ROW LEVEL SECURITY;
    """)

    # Step 5: Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY dc_channel_user_isolation_policy ON dc_channel_measurements
            FOR ALL
            USING (user_id = current_setting('app.current_user_id', true)::int);
    """)

    # Step 6: Set retention policy (2 years)
    op.execute("""
        SELECT add_retention_policy('dc_channel_measurements', INTERVAL '730 days');
    """)


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS dc_channel_user_isolation_policy ON dc_channel_measurements;")

    # Drop indexes (they'll be dropped with the table, but explicit for clarity)
    op.execute("DROP INDEX IF EXISTS idx_dc_channel;")
    op.execute("DROP INDEX IF EXISTS idx_dc_inverter_time;")
    op.execute("DROP INDEX IF EXISTS idx_dc_user_time;")

    # Drop table (also removes hypertable and retention policy)
    op.drop_table('dc_channel_measurements')
