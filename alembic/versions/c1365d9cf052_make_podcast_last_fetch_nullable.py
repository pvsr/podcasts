"""make podcast last_fetch nullable

Revision ID: c1365d9cf052
Revises 20e538e132db
Create Date: 2022-12-27 14:30:08.261900

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1365d9cf052"
down_revision = "20e538e132db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("podcast") as batch_op:
        batch_op.alter_column("last_fetch", nullable=True)


def downgrade() -> None:
    pass
