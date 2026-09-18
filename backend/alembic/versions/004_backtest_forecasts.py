"""backtest_forecasts table for walk-forward simulation

Revision ID: 004_backtest_forecasts
Revises: 003_instrument_kind
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_backtest_forecasts"
down_revision: Union[str, None] = "003_instrument_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.Integer(),
            sa.ForeignKey("instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("expected_change_pct", sa.Float(), nullable=True),
        sa.Column("range_low_pct", sa.Float(), nullable=True),
        sa.Column("range_high_pct", sa.Float(), nullable=True),
        sa.Column("spot_price", sa.Float(), nullable=False),
        sa.Column("path_json", sa.Text(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("news_vs_chart", sa.String(length=16), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "as_of", name="uq_backtest_inst_asof"),
    )
    op.create_index("ix_backtest_forecasts_instrument_id", "backtest_forecasts", ["instrument_id"])
    op.create_index("ix_backtest_forecasts_as_of", "backtest_forecasts", ["as_of"])


def downgrade() -> None:
    op.drop_index("ix_backtest_forecasts_as_of", table_name="backtest_forecasts")
    op.drop_index("ix_backtest_forecasts_instrument_id", table_name="backtest_forecasts")
    op.drop_table("backtest_forecasts")
