"""add_yield_fields_to_inverter_measurements

Revision ID: d8f09ab046bf
Revises: 687924fcd12d
Create Date: 2025-10-22 11:55:32.635700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f09ab046bf'
down_revision: Union[str, None] = '687924fcd12d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add yield fields to inverter_measurements table
    op.add_column('inverter_measurements', sa.Column('yield_day_wh', sa.Integer(), nullable=True))
    op.add_column('inverter_measurements', sa.Column('yield_total_kwh', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop yield fields from inverter_measurements table
    op.drop_column('inverter_measurements', 'yield_total_kwh')
    op.drop_column('inverter_measurements', 'yield_day_wh')
