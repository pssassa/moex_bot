"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("shortname", sa.String(255), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("isin", sa.String(32), nullable=False),
        sa.Column("is_russian", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("board", sa.String(16), nullable=False, server_default="TQBR"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="SUR"),
        sa.Column("list_level", sa.Integer(), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("emitent_title", sa.String(512), nullable=True),
        sa.Column("sec_type", sa.String(64), nullable=True),
        sa.Column("last_close", sa.Float(), nullable=True),
        sa.Column("last_change_pct", sa.Float(), nullable=True),
        sa.Column("last_candle_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_instruments_ticker", "instruments", ["ticker"], unique=True)
    op.create_index("ix_instruments_isin", "instruments", ["isin"])

    op.create_table(
        "candles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_candles_inst_tf_ts"),
    )
    op.create_index("ix_candles_instrument_id", "candles", ["instrument_id"])
    op.create_index("ix_candles_ts", "candles", ["ts"])

    op.create_table(
        "macro_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imoex", sa.Float(), nullable=True),
        sa.Column("imoex_change_pct", sa.Float(), nullable=True),
        sa.Column("rtsi", sa.Float(), nullable=True),
        sa.Column("rtsi_change_pct", sa.Float(), nullable=True),
        sa.Column("usd_rub", sa.Float(), nullable=True),
        sa.Column("usd_rub_change_pct", sa.Float(), nullable=True),
        sa.Column("cny_rub", sa.Float(), nullable=True),
        sa.Column("cny_rub_change_pct", sa.Float(), nullable=True),
        sa.Column("rgbi", sa.Float(), nullable=True),
        sa.Column("rgbi_change_pct", sa.Float(), nullable=True),
        sa.Column("cbr_key_rate", sa.Float(), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="iss"),
    )
    op.create_index("ix_macro_snapshots_ts", "macro_snapshots", ["ts"])

    op.create_table(
        "news",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("lang", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("is_world", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url", name="uq_news_url"),
    )
    op.create_index("ix_news_published_at", "news", ["published_at"])
    op.create_index("ix_news_source", "news", ["source"])

    op.create_table(
        "news_instruments",
        sa.Column("news_id", sa.Integer(), sa.ForeignKey("news.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("news_factors", sa.Text(), nullable=True),
        sa.Column("macro_factors", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_forecasts_instrument_id", "forecasts", ["instrument_id"])
    op.create_index("ix_forecasts_created_at", "forecasts", ["created_at"])

    op.create_table(
        "sync_state",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("detail", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_table("forecasts")
    op.drop_table("news_instruments")
    op.drop_table("news")
    op.drop_table("macro_snapshots")
    op.drop_table("candles")
    op.drop_table("instruments")
