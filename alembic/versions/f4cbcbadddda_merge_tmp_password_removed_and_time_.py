"""merge tmp_password removed and time-series table

Revision ID: f4cbcbadddda
Revises: b7c96dc8da99, f16b15d226cd
Create Date: 2025-10-20 23:35:20.549762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4cbcbadddda'
down_revision: Union[str, None] = ('b7c96dc8da99', 'f16b15d226cd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
