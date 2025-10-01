"""Add RoadEdge canonicalization constraint

Revision ID: 91831d69ddfb
Revises: 81c03d2e48d8
Create Date: 2025-09-30 23:02:09.365921

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91831d69ddfb'
down_revision: Union[str, Sequence[str], None] = '81c03d2e48d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite requires batch mode for constraint changes
    with op.batch_alter_table('road_edges', schema=None) as batch_op:
        # Drop old unique constraint
        batch_op.drop_constraint('uq_road_edges', type_='unique')
        # Add new unique constraint with updated name
        batch_op.create_unique_constraint('uq_road_edges_hexes', ['game_id', 'from_hex_id', 'to_hex_id'])
        # Add CHECK constraint for canonical ordering
        batch_op.create_check_constraint('ck_road_edges_order', 'from_hex_id < to_hex_id')


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite requires batch mode for constraint changes
    with op.batch_alter_table('road_edges', schema=None) as batch_op:
        # Drop CHECK constraint
        batch_op.drop_constraint('ck_road_edges_order', type_='check')
        # Drop new unique constraint
        batch_op.drop_constraint('uq_road_edges_hexes', type_='unique')
        # Restore old unique constraint
        batch_op.create_unique_constraint('uq_road_edges', ['game_id', 'from_hex_id', 'to_hex_id'])
