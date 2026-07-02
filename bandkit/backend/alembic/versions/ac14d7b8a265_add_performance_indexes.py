"""add performance indexes

Revision ID: ac14d7b8a265
Revises: 1707e1730c63
Create Date: 2026-05-01 23:40:52.612212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac14d7b8a265'
down_revision: Union[str, Sequence[str], None] = '1707e1730c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_events_date",        "events",        ["date"])
    op.create_index("ix_songs_title",         "songs",         ["title"])
    op.create_index("ix_setlist_items_event", "setlist_items", ["event_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_setlist_items_event", table_name="setlist_items")
    op.drop_index("ix_songs_title",         table_name="songs")
    op.drop_index("ix_events_date",         table_name="events")
