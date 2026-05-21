"""add indexes on foreign keysv2

Revision ID: 60a4cd8e4902
Revises: 7bb11ce38361
Create Date: 2026-05-21 13:47:31.448654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60a4cd8e4902'
down_revision: Union[str, Sequence[str], None] = '7bb11ce38361'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_ratings_user_id", "ratings", ["user_id"])
    op.create_index("ix_ratings_movie_id", "ratings", ["movie_id"])
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])
    op.create_index("ix_watchlist_movie_id", "watchlist", ["movie_id"])

def downgrade() -> None:
    op.drop_index("ix_ratings_user_id", "ratings")
    op.drop_index("ix_ratings_movie_id", "ratings")
    op.drop_index("ix_watchlist_user_id", "watchlist")
    op.drop_index("ix_watchlist_movie_id", "watchlist")