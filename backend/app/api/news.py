from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import NewsItem
from app.schemas import NewsOut

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsOut])
def list_news(
    world: bool | None = None,
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[NewsOut]:
    query = db.query(NewsItem)
    if world is True:
        query = query.filter(NewsItem.is_world.is_(True))
    elif world is False:
        query = query.filter(NewsItem.is_world.is_(False))
    rows = query.order_by(NewsItem.published_at.desc().nullslast()).limit(limit).all()
    result: list[NewsOut] = []
    for item in rows:
        result.append(
            NewsOut(
                id=item.id,
                source=item.source,
                title=item.title,
                url=item.url,
                published_at=item.published_at,
                summary=item.summary,
                is_world=item.is_world,
                tickers=[inst.ticker for inst in item.instruments],
            )
        )
    return result
