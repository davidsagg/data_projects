"""refactor setlist execution model

Revision ID: b9cff16f859b
Revises: ac14d7b8a265
Create Date: 2026-05-03 19:23:40.320021

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9cff16f859b'
down_revision: Union[str, Sequence[str], None] = 'ac14d7b8a265'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove tabelas antigas se existirem (tolerante a DBs em estados diferentes)
    conn = op.get_bind()
    existing = sa.inspect(conn).get_table_names()
    if 'setlist_musicians' in existing:
        op.drop_table('setlist_musicians')
    if 'setlist_items' in existing:
        op.drop_table('setlist_items')
    # Remove tabelas da refatoração intermediária se já existirem
    for t in ['execution_musicians', 'musical_executions', 'setlist_songs', 'setlists']:
        if t in existing:
            op.drop_table(t)
    if 'setlist_id' in {c['name'] for c in sa.inspect(conn).get_columns('events')}:
        with op.batch_alter_table('events') as _b:
            _b.drop_column('setlist_id')

    # Setlists — entidade independente, reutilizável entre eventos
    op.create_table(
        'setlists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )

    # SetlistSong — músicas de um setlist com ordem
    op.create_table(
        'setlist_songs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('setlist_id', sa.Integer(), sa.ForeignKey('setlists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('song_id', sa.Integer(), sa.ForeignKey('songs.id'), nullable=False),
        sa.Column('order_position', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.UniqueConstraint('setlist_id', 'order_position', name='uq_setlist_song_pos'),
    )
    op.create_index('ix_setlist_songs_setlist', 'setlist_songs', ['setlist_id'])

    # Evento referencia Setlist (batch mode para SQLite)
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(sa.Column('setlist_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_events_setlist', 'setlists', ['setlist_id'], ['id'], ondelete='SET NULL')

    # MusicalExecution — execução de uma música em um evento
    op.create_table(
        'musical_executions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('song_id', sa.Integer(), sa.ForeignKey('songs.id'), nullable=False),
        sa.Column('key_override', sa.String(10), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.UniqueConstraint('event_id', 'song_id', name='uq_execution'),
    )
    op.create_index('ix_executions_event', 'musical_executions', ['event_id'])

    # ExecutionMusician — músico em uma execução
    op.create_table(
        'execution_musicians',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('musical_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('musician_id', sa.Integer(), sa.ForeignKey('musicians.id'), nullable=False),
        sa.Column('instrument_override', sa.String(80), nullable=True),
        sa.UniqueConstraint('execution_id', 'musician_id', name='uq_exec_musician'),
    )


def downgrade() -> None:
    op.drop_table('execution_musicians')
    op.drop_table('musical_executions')
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_constraint('fk_events_setlist', type_='foreignkey')
        batch_op.drop_column('setlist_id')
    op.drop_index('ix_setlist_songs_setlist', table_name='setlist_songs')
    op.drop_table('setlist_songs')
    op.drop_table('setlists')
    op.create_table(
        'setlist_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('song_id', sa.Integer(), sa.ForeignKey('songs.id'), nullable=False),
        sa.Column('order_position', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('key_override', sa.String(10), nullable=True),
        sa.UniqueConstraint('event_id', 'order_position', name='uq_setlist_position'),
    )
    op.create_table(
        'setlist_musicians',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('setlist_item_id', sa.Integer(), sa.ForeignKey('setlist_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('musician_id', sa.Integer(), sa.ForeignKey('musicians.id'), nullable=False),
        sa.Column('instrument_override', sa.String(80), nullable=True),
        sa.UniqueConstraint('setlist_item_id', 'musician_id', name='uq_setlist_musician'),
    )
