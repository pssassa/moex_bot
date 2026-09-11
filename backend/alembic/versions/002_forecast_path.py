"""forecast path and chart analysis

Revision ID: 002_forecast_path
Revises: 001_initial
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_forecast_path"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forecasts", sa.Column("chart_analysis", sa.Text(), nullable=True))
    op.add_column("forecasts", sa.Column("news_alignment", sa.Text(), nullable=True))
    op.add_column("forecasts", sa.Column("news_vs_chart", sa.String(length=16), nullable=True))
    op.add_column("forecasts", sa.Column("expected_change_pct", sa.Float(), nullable=True))
    op.add_column("forecasts", sa.Column("range_low_pct", sa.Float(), nullable=True))
    op.add_column("forecasts", sa.Column("range_high_pct", sa.Float(), nullable=True))
    op.add_column("forecasts", sa.Column("horizon_days", sa.Integer(), nullable=True))
    op.add_column("forecasts", sa.Column("spot_price", sa.Float(), nullable=True))
    op.add_column("forecasts", sa.Column("path_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("forecasts", "path_json")
    op.drop_column("forecasts", "spot_price")
    op.drop_column("forecasts", "horizon_days")
    op.drop_column("forecasts", "range_high_pct")
    op.drop_column("forecasts", "range_low_pct")
    op.drop_column("forecasts", "expected_change_pct")
    op.drop_column("forecasts", "news_vs_chart")
    op.drop_column("forecasts", "news_alignment")
    op.drop_column("forecasts", "chart_analysis")
