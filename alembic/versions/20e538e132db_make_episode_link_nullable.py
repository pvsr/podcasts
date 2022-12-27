"""make episode link nullable

Revision ID: 20e538e132db
Revises: 
Create Date: 2022-12-27 13:49:13.630583

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20e538e132db"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("episode") as batch_op:
        batch_op.alter_column("link", nullable=True)


def downgrade() -> None:
    pass
