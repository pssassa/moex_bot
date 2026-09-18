from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.backtest import router as backtest_router
from app.api.forecast import router as forecast_router
from app.api.health import router as health_router
from app.api.instruments import router as instruments_router
from app.api.macro import router as macro_router
from app.api.news import router as news_router

app = FastAPI(title="MOEX Analyst", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(instruments_router, prefix="/api")
app.include_router(news_router, prefix="/api")
app.include_router(macro_router, prefix="/api")
app.include_router(forecast_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
