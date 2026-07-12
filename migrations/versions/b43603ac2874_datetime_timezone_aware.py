"""datetime timezone aware

Revision ID: b43603ac2874
Revises: 9dd869f9ccd8
Create Date: 2026-07-12 15:18:12.782129

"""
from alembic import op
import sqlalchemy as sa


revision = 'b43603ac2874'
down_revision = '9dd869f9ccd8'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('user', 'code_expiration',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True)
    op.alter_column('user', 'reset_code_expiration',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True)
    op.alter_column('reservation', 'date_reservation',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True)
    op.alter_column('trajet_log', 'timestamp',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True)
    op.alter_column('avis', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True)


def downgrade():
    op.alter_column('avis', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True)
    op.alter_column('trajet_log', 'timestamp',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True)
    op.alter_column('reservation', 'date_reservation',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True)
    op.alter_column('user', 'reset_code_expiration',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True)
    op.alter_column('user', 'code_expiration',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True)
