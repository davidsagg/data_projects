"""add order_position to musical_executions

Revision ID: 1eed9e735767
Revises: b9cff16f859b
Create Date: 2026-05-10 03:02:38.440692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1eed9e735767'
down_revision: Union[str, Sequence[str], None] = 'b9cff16f859b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('musical_executions') as batch_op:
        batch_op.add_column(sa.Column('order_position', sa.Integer(), nullable=True))
    # Backfill: cada evento recebe posições 1..N na ordem de inserção (id)
    op.execute("""
        UPDATE musical_executions
        SET order_position = (
            SELECT COUNT(*)
            FROM musical_executions me2
            WHERE me2.event_id = musical_executions.event_id
              AND me2.id <= musical_executions.id
        )
    """)


def downgrade() -> None:
    with op.batch_alter_table('musical_executions') as batch_op:
        batch_op.drop_column('order_position')
