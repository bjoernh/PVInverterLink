"""Add time-series table and remove InfluxDB fields

Revision ID: b7c96dc8da99
Revises: 1d006d59a0fb
Create Date: 2025-10-17 12:47:01.386810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c96dc8da99'
down_revision: Union[str, None] = '1d006d59a0fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Remove InfluxDB fields from User table
    op.drop_column('user', 'influx_url')
    op.drop_column('user', 'influx_org_id')
    op.drop_column('user', 'influx_token')
    # Note: Keeping tmp_pass as it may be used for other purposes

    # Step 2: Remove InfluxDB fields from Inverter table
    op.drop_column('inverter', 'influx_bucked_id')

    # Step 3: Create time-series measurements table
    op.create_table(
        'inverter_measurements',
        sa.Column('time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('inverter_id', sa.Integer(), nullable=False),
        sa.Column('total_output_power', sa.Integer(), nullable=False),
        # Optional: Add more measurement fields as needed
        # sa.Column('grid_voltage', sa.Numeric(6, 2), nullable=True),
        # sa.Column('grid_frequency', sa.Numeric(5, 2), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inverter_id'], ['inverter.id'], ondelete='CASCADE'),
    )

    # Step 4: Convert to TimescaleDB hypertable with multi-dimensional partitioning
    op.execute("""
        SELECT create_hypertable(
            'inverter_measurements',
            'time',
            partitioning_column => 'user_id',
            number_partitions => 4,
            chunk_time_interval => INTERVAL '7 days'
        );
    """)

    # Step 5: Create indexes for performance
    op.execute("""
        CREATE INDEX idx_user_time ON inverter_measurements (user_id, time DESC);
    """)
    op.execute("""
        CREATE INDEX idx_inverter_time ON inverter_measurements (inverter_id, time DESC);
    """)

    # Step 6: NOTE: Compression disabled due to incompatibility with RLS in TimescaleDB
    # RLS is more important for multi-tenant security than compression
    # Compression can be enabled in future if:
    # - TimescaleDB adds support for compression + RLS
    # - OR we decide to use application-level security only

    # Step 7: Enable Row-Level Security
    op.execute("""
        ALTER TABLE inverter_measurements ENABLE ROW LEVEL SECURITY;
    """)

    # Step 8: Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY user_isolation_policy ON inverter_measurements
            FOR ALL
            USING (user_id = current_setting('app.current_user_id', true)::int);
    """)

    # Step 9: Set retention policy (2 years)
    op.execute("""
        SELECT add_retention_policy('inverter_measurements', INTERVAL '730 days');
    """)


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS user_isolation_policy ON inverter_measurements;")

    # Drop indexes (they'll be dropped with the table, but explicit for clarity)
    op.execute("DROP INDEX IF EXISTS idx_inverter_time;")
    op.execute("DROP INDEX IF EXISTS idx_user_time;")

    # Drop table (also removes hypertable, compression, and retention policies)
    op.drop_table('inverter_measurements')

    # Restore InfluxDB fields to Inverter
    op.add_column('inverter', sa.Column('influx_bucked_id', sa.String(), nullable=True))

    # Restore InfluxDB fields to User
    op.add_column('user', sa.Column('influx_token', sa.String(), nullable=True))
    op.add_column('user', sa.Column('influx_org_id', sa.String(), nullable=True))
    op.add_column('user', sa.Column('influx_url', sa.String(64), nullable=True))
