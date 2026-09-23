from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.models import Candle

HORIZON = 5
WARMUP = 60
MAX_DAILY_MOVE = 0.30  # больший дневной ход считаем сплитом/артефактом и выкидываем окно
MIN_CROSS_SECTION = 10  # минимум акций в дне, чтобы считать рыночные признаки
MIN_TURNOVER_RUB = 5_000_000  # медианный оборот за 20 сессий; ниже цена «застаивается» и шумит
MIN_VOL60_PCT = 0.1  # дневная волатильность ниже — фонд денежного рынка, его рост тривиален
Z80 = 1.2816  # квантиль нормального распределения для 80% интервала
QUANTILES = (0.1, 0.5, 0.9)

KINDS = ("share", "fund", "metal")
KIND_CODE = {name: code for code, name in enumerate(KINDS)}

BASE_FEATURES = [
    "r1", "r5", "r10", "r20", "r60",
    "vol10", "vol20", "vol60", "atr_pct", "rsi14",
    "dist_sma20", "dist_sma50", "sma20_vs_50",
    "dist_high20", "dist_low20", "range_pos20",
    "vol_ratio", "gap", "dow", "log_turnover20",
]
CROSS_FEATURES = ["mkt_r5", "mkt_r20", "mkt_vol20", "rel_r5", "rel_r20"]
KIND_FEATURES = ["is_fund", "is_metal"]
FEATURES = BASE_FEATURES + CROSS_FEATURES + KIND_FEATURES
VOL20_COL = FEATURES.index("vol20")
R5_COL = FEATURES.index("r5")


@dataclass
class Dataset:
    X: np.ndarray
    ret5: np.ndarray  # фактический ход за HORIZON сессий в %, NaN если ещё неизвестен
    rank: np.ndarray  # порядковый номер торгового дня
    dates: np.ndarray  # datetime64[D] для каждой строки
    inst_id: np.ndarray
    kind: np.ndarray  # код из KIND_CODE
    unique_dates: np.ndarray
    skipped: dict[str, int]  # инструменты без единой пригодной строки, по классам


def _roll_mean(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        cs = np.concatenate(([0.0], np.cumsum(x)))
        out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def _roll_std(x: np.ndarray, w: int) -> np.ndarray:
    mean = _roll_mean(x, w)
    mean_sq = _roll_mean(x * x, w)
    return np.sqrt(np.clip(mean_sq - mean * mean, 0.0, None))


def _roll_apply(x: np.ndarray, w: int, fn) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = fn(sliding_window_view(x, w), axis=1)
    return out


def _shift_pct(c: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(c), np.nan)
    out[k:] = (c[k:] / c[:-k] - 1.0) * 100.0
    return out


def _instrument_block(candles: list[Candle]) -> dict | None:
    n = len(candles)
    if n < WARMUP + HORIZON + 2:
        return None
    o = np.array([c.open for c in candles], dtype=float)
    h = np.array([c.high for c in candles], dtype=float)
    lo = np.array([c.low for c in candles], dtype=float)
    c = np.array([c.close for c in candles], dtype=float)
    v = np.nan_to_num(
        np.array([np.nan if x.volume is None else x.volume for x in candles], dtype=float), nan=0.0
    )
    # по металлам (CETS) ISS не отдаёт ни оборот, ни объём, хотя сделок там сотни-тысячи в день
    has_turnover = any(x.value is not None for x in candles)
    turnover = np.nan_to_num(
        np.array([np.nan if x.value is None else x.value for x in candles], dtype=float), nan=0.0
    )
    if not (np.all(c > 0) and np.all(np.isfinite(c))):
        return None

    prev_c = np.concatenate(([c[0]], c[:-1]))
    log_ret = np.log(c / prev_c)
    daily = c / prev_c - 1.0
    bad = np.abs(daily) > MAX_DAILY_MOVE
    bad[0] = False
    bad_cs = np.concatenate(([0], np.cumsum(bad)))

    tr = np.maximum.reduce([h - lo, np.abs(h - prev_c), np.abs(lo - prev_c)])
    atr_pct = _roll_mean(tr, 14) / c * 100.0

    diff = c - prev_c
    gains = _roll_mean(np.clip(diff, 0.0, None), 14)
    losses = _roll_mean(np.clip(-diff, 0.0, None), 14)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = gains / losses
        rsi = np.where(losses == 0, np.where(gains == 0, 50.0, 100.0), 100.0 - 100.0 / (1.0 + rs))

    sma20 = _roll_mean(c, 20)
    sma50 = _roll_mean(c, 50)
    hi20 = _roll_apply(h, 20, np.max)
    lo20 = _roll_apply(lo, 20, np.min)
    turnover20 = _roll_apply(turnover, 20, np.median)
    vol_sma = _roll_mean(v, 20)
    with np.errstate(divide="ignore", invalid="ignore"):
        vol_ratio = np.where(vol_sma > 0, v / vol_sma, 1.0)
        range_pos = np.where(hi20 > lo20, (c - lo20) / (hi20 - lo20), 0.5)

    feats = {
        "r1": _shift_pct(c, 1),
        "r5": _shift_pct(c, 5),
        "r10": _shift_pct(c, 10),
        "r20": _shift_pct(c, 20),
        "r60": _shift_pct(c, 60),
        "vol10": _roll_std(log_ret, 10) * 100.0,
        "vol20": _roll_std(log_ret, 20) * 100.0,
        "vol60": _roll_std(log_ret, 60) * 100.0,
        "atr_pct": atr_pct,
        "rsi14": rsi,
        "dist_sma20": (c / sma20 - 1.0) * 100.0,
        "dist_sma50": (c / sma50 - 1.0) * 100.0,
        "sma20_vs_50": (sma20 / sma50 - 1.0) * 100.0,
        "dist_high20": (hi20 / c - 1.0) * 100.0,
        "dist_low20": (c / lo20 - 1.0) * 100.0,
        "range_pos20": range_pos,
        "vol_ratio": vol_ratio,
        "gap": (o / prev_c - 1.0) * 100.0,
        "dow": np.array([x.ts.weekday() for x in candles], dtype=float),
        "log_turnover20": np.log10(turnover20 + 1.0),
    }

    ret5 = np.full(n, np.nan)
    ret5[: n - HORIZON] = (c[HORIZON:] / c[:-HORIZON] - 1.0) * 100.0

    idx = np.arange(WARMUP, n)
    hi_idx = np.minimum(idx + HORIZON, n - 1)
    clean = (bad_cs[hi_idx + 1] - bad_cs[idx - WARMUP]) == 0
    with np.errstate(invalid="ignore"):
        liquid = turnover20 >= MIN_TURNOVER_RUB if has_turnover else np.ones(n, dtype=bool)
        tradable = liquid & (feats["vol60"] >= MIN_VOL60_PCT)
    idx = idx[clean & tradable[idx]]
    return {
        "X": np.column_stack([feats[name][idx] for name in BASE_FEATURES]),
        "ret5": ret5[idx],
        "dates": np.array([np.datetime64(candles[i].ts.date()) for i in idx]),
    }


def build_dataset(series: dict[int, list[Candle]], kinds: dict[int, str]) -> Dataset:
    """`kinds` — класс актива для каждого инструмента выборки; инструменты без свечей
    или без единой ликвидной строки попадают в `skipped`."""
    xs, ys, dates, ids, codes = [], [], [], [], []
    skipped: dict[str, int] = {}
    for inst_id, kind in kinds.items():
        block = _instrument_block(series.get(inst_id, []))
        if block is None or len(block["ret5"]) == 0:
            skipped[kind] = skipped.get(kind, 0) + 1
            continue
        xs.append(block["X"])
        ys.append(block["ret5"])
        dates.append(block["dates"])
        ids.append(np.full(len(block["ret5"]), inst_id))
        codes.append(np.full(len(block["ret5"]), KIND_CODE[kind]))
    if not xs:
        raise ValueError("Нет данных: сначала выполните `python -m app.quant_cli sync`")

    X = np.vstack(xs)
    ret5 = np.concatenate(ys)
    row_dates = np.concatenate(dates)
    inst_id = np.concatenate(ids)
    kind = np.concatenate(codes)
    is_share = kind == KIND_CODE["share"]

    _, rank = np.unique(row_dates, return_inverse=True)
    share_counts = np.bincount(rank, weights=is_share.astype(float))

    # «рынок» — средние по акциям IMOEX в тот же день: одинаковая точка отсчёта для всех классов
    def market_mean(col: str) -> np.ndarray:
        values = X[:, BASE_FEATURES.index(col)]
        use = np.isfinite(values) & is_share
        sums = np.bincount(rank, weights=np.where(use, values, 0.0))
        cnt = np.bincount(rank, weights=use.astype(float))
        with np.errstate(divide="ignore", invalid="ignore"):
            means = sums / cnt
        return means[rank]

    mkt_r5 = market_mean("r5")
    mkt_r20 = market_mean("r20")
    mkt_vol20 = market_mean("vol20")
    cross = np.column_stack(
        [
            mkt_r5,
            mkt_r20,
            mkt_vol20,
            X[:, BASE_FEATURES.index("r5")] - mkt_r5,
            X[:, BASE_FEATURES.index("r20")] - mkt_r20,
        ]
    )
    kind_cols = np.column_stack(
        [(kind == KIND_CODE["fund"]).astype(float), (kind == KIND_CODE["metal"]).astype(float)]
    )
    X = np.hstack([X, cross, kind_cols])

    keep = np.isfinite(X).all(axis=1) & (share_counts[rank] >= MIN_CROSS_SECTION)
    unique_dates, rank = np.unique(row_dates[keep], return_inverse=True)
    return Dataset(
        X=X[keep],
        ret5=ret5[keep],
        rank=rank,
        dates=row_dates[keep],
        inst_id=inst_id[keep],
        kind=kind[keep],
        unique_dates=unique_dates,
        skipped=skipped,
    )


def _direction_models() -> dict:
    return {
        "logreg": make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=500)),
        "gb": HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=150,
            min_samples_leaf=100,
            l2_regularization=1.0,
            random_state=0,
        ),
    }


def _quantile_model(q: float) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="quantile",
        quantile=q,
        max_depth=3,
        learning_rate=0.05,
        max_iter=150,
        min_samples_leaf=100,
        l2_regularization=1.0,
        random_state=0,
    )


def _pinball(y: np.ndarray, f: np.ndarray, alpha: float) -> float:
    d = y - f
    return float(np.mean(np.maximum(alpha * d, (alpha - 1.0) * d)))


def _winkler(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, alpha: float = 0.2) -> float:
    penalty = (2.0 / alpha) * (np.maximum(lo - y, 0.0) + np.maximum(y - hi, 0.0))
    return float(np.mean((hi - lo) + penalty))


def _block_bootstrap_edge(
    correct_model: np.ndarray,
    correct_base: np.ndarray,
    rank: np.ndarray,
    block: int = HORIZON,
    n_boot: int = 1000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Разница точности модель − бейзлайн с доверительным интервалом. Ресемплинг идёт
    блоками по датам, чтобы учесть пересечение 5-дневных окон и общий рыночный фактор."""
    r = rank - rank.min()
    days = int(r.max()) + 1
    m = np.bincount(r, weights=correct_model.astype(float), minlength=days)
    b = np.bincount(r, weights=correct_base.astype(float), minlength=days)
    n = np.bincount(r, minlength=days).astype(float)
    n_blocks = int(np.ceil(days / block))
    pad = n_blocks * block - days

    def blocks(a: np.ndarray) -> np.ndarray:
        return np.concatenate([a, np.zeros(pad)]).reshape(n_blocks, block).sum(axis=1)

    mb, bb, nb = blocks(m), blocks(b), blocks(n)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, n_blocks, size=(n_boot, n_blocks))
    diffs = (mb[pick].sum(axis=1) - bb[pick].sum(axis=1)) / nb[pick].sum(axis=1)
    point = float((mb.sum() - bb.sum()) / nb.sum())
    return point, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _direction_report(y: np.ndarray, p: np.ndarray, p0: np.ndarray, r5: np.ndarray, rank: np.ndarray) -> dict:
    eps = 1e-6
    pc = np.clip(p, eps, 1 - eps)
    p0c = np.clip(p0, eps, 1 - eps)
    correct = (p > 0.5) == (y == 1)
    always_up = y == 1
    momentum = (r5 > 0) == (y == 1)
    base_correct = always_up if always_up.mean() >= momentum.mean() else momentum
    base_name = "always_up" if always_up.mean() >= momentum.mean() else "momentum"
    edge, lo, hi = _block_bootstrap_edge(correct, base_correct, rank)
    return {
        "accuracy": round(float(correct.mean()), 4),
        "auc": round(float(roc_auc_score(y, p)), 4),
        "brier": round(float(np.mean((p - y) ** 2)), 5),
        "brier_constant": round(float(np.mean((p0 - y) ** 2)), 5),
        "logloss": round(float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))), 5),
        "logloss_constant": round(float(-np.mean(y * np.log(p0c) + (1 - y) * np.log(1 - p0c))), 5),
        "best_baseline": base_name,
        "edge_vs_best_baseline": round(edge, 4),
        "edge_ci95": [round(lo, 4), round(hi, 4)],
    }


def _abstention_table(y: np.ndarray, p: np.ndarray, r5: np.ndarray) -> list[dict]:
    conf = np.abs(p - 0.5)
    rows = []
    for threshold in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        mask = conf >= threshold
        if mask.sum() < 30:
            continue
        rows.append(
            {
                "min_confidence": threshold,
                "coverage": round(float(mask.mean()), 3),
                "n": int(mask.sum()),
                "accuracy": round(float(np.mean((p[mask] > 0.5) == (y[mask] == 1))), 4),
                "momentum_accuracy": round(float(np.mean((r5[mask] > 0) == (y[mask] == 1))), 4),
                "always_up_accuracy": round(float(np.mean(y[mask] == 1)), 4),
            }
        )
    return rows


def _interval_report(y: np.ndarray, q: np.ndarray, vol20: np.ndarray, fold: np.ndarray) -> dict:
    lo, med, hi = q
    sigma = vol20 * np.sqrt(HORIZON)
    lo_b, hi_b, med_b = -Z80 * sigma, Z80 * sigma, np.zeros_like(y)

    def summary(l: np.ndarray, m: np.ndarray, h: np.ndarray) -> dict:
        return {
            "coverage_80": round(float(np.mean((y >= l) & (y <= h))), 4),
            "mean_width_pct": round(float(np.mean(h - l)), 3),
            "winkler_80": round(_winkler(y, l, h), 4),
            "pinball_q10": round(_pinball(y, l, 0.1), 4),
            "pinball_q50": round(_pinball(y, m, 0.5), 4),
            "pinball_q90": round(_pinball(y, h, 0.9), 4),
            "mae_median": round(float(np.mean(np.abs(y - m))), 4),
        }

    per_fold = []
    for k in np.unique(fold):
        mask = fold == k
        per_fold.append(round(float(np.mean((y[mask] >= lo[mask]) & (y[mask] <= hi[mask]))), 3))
    return {
        "model": summary(lo, med, hi),
        "baseline_vol20": summary(lo_b, med_b, hi_b),
        "model_coverage_per_fold": per_fold,
    }


def _daily_ic(p: np.ndarray, y_ret: np.ndarray, rank: np.ndarray, min_n: int = 10) -> dict:
    """Ранговая корреляция прогноза и факта внутри каждого дня: показывает умение
    выбирать бумаги, а не просто угадывать общее движение рынка."""
    order = np.argsort(rank, kind="stable")
    bounds = np.flatnonzero(np.diff(rank[order])) + 1
    ics = []
    for group in np.split(order, bounds):
        if len(group) < min_n:
            continue
        a = np.argsort(np.argsort(p[group])).astype(float)
        b = np.argsort(np.argsort(y_ret[group])).astype(float)
        if a.std() == 0 or b.std() == 0:
            continue
        ics.append(np.corrcoef(a, b)[0, 1])
    if not ics:
        return {"days": 0}
    ics_arr = np.array(ics)
    n_eff = max(len(ics_arr) / HORIZON, 1.0)
    std = float(ics_arr.std()) or 1e-9
    return {
        "days": int(len(ics_arr)),
        "mean_ic": round(float(ics_arr.mean()), 4),
        "share_days_positive": round(float((ics_arr > 0).mean()), 3),
        "t_stat_overlap_adjusted": round(float(ics_arr.mean() / (std / np.sqrt(n_eff))), 2),
    }


def _kind_report(
    mask: np.ndarray,
    y: np.ndarray,
    y_ret: np.ndarray,
    p: np.ndarray,
    r5: np.ndarray,
    rank: np.ndarray,
    inst: np.ndarray,
    q: np.ndarray,
    vol20: np.ndarray,
) -> dict:
    y_k, yr = y[mask], y_ret[mask]
    correct = (p[mask] > 0.5) == (y_k == 1)
    always_up = y_k == 1
    momentum = (r5[mask] > 0) == (y_k == 1)
    use_up = always_up.mean() >= momentum.mean()
    edge, ci_lo, ci_hi = _block_bootstrap_edge(correct, always_up if use_up else momentum, rank[mask])
    lo, _, hi = q[:, mask]
    band = Z80 * vol20[mask] * np.sqrt(HORIZON)
    report = {
        "instruments": int(len(np.unique(inst[mask]))),
        "test_rows": int(mask.sum()),
        "accuracy": round(float(correct.mean()), 4),
        "always_up_accuracy": round(float(always_up.mean()), 4),
        "momentum_accuracy": round(float(momentum.mean()), 4),
        "best_baseline": "always_up" if use_up else "momentum",
        "edge_vs_best_baseline": round(edge, 4),
        "edge_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
        "interval_80": {
            "model_coverage": round(float(np.mean((yr >= lo) & (yr <= hi))), 4),
            "model_width_pct": round(float(np.mean(hi - lo)), 3),
            "model_winkler": round(_winkler(yr, lo, hi), 3),
            "vol20_coverage": round(float(np.mean(np.abs(yr) <= band)), 4),
            "vol20_width_pct": round(float(np.mean(2 * band)), 3),
            "vol20_winkler": round(_winkler(yr, -band, band), 3),
        },
    }
    ic = _daily_ic(p[mask], yr, rank[mask])
    if ic["days"]:
        report["cross_sectional_ic"] = ic
    return report


def evaluate(ds: Dataset, test_days: int = 160, folds: int = 4) -> dict:
    labeled = np.isfinite(ds.ret5)
    max_rank = int(ds.rank[labeled].max())
    test_start = max_rank - test_days + 1
    if test_start < 250:
        raise ValueError(
            "Мало истории для честного теста: нужно минимум ~250 торговых дней до тестового периода. "
            "Выполните `python -m app.quant_cli sync` для догрузки свечей."
        )
    edges = np.linspace(test_start, max_rank + 1, folds + 1).astype(int)

    test_idx, fold_id, p_by_model, quant, p0_rows = [], [], {}, [], []
    for k in range(folds):
        lo, hi = edges[k], edges[k + 1]
        train = labeled & (ds.rank < lo - HORIZON)
        test = labeled & (ds.rank >= lo) & (ds.rank < hi)
        if train.sum() < 1000 or test.sum() == 0:
            continue
        y_train = (ds.ret5[train] > 0).astype(int)
        for name, model in _direction_models().items():
            model.fit(ds.X[train], y_train)
            p_by_model.setdefault(name, []).append(model.predict_proba(ds.X[test])[:, 1])
        preds = []
        for q in QUANTILES:
            reg = _quantile_model(q)
            reg.fit(ds.X[train], ds.ret5[train])
            preds.append(reg.predict(ds.X[test]))
        quant.append(np.sort(np.vstack(preds), axis=0))
        test_idx.append(np.flatnonzero(test))
        fold_id.append(np.full(test.sum(), k))
        p0_rows.append(np.full(test.sum(), y_train.mean()))

    idx = np.concatenate(test_idx)
    fold = np.concatenate(fold_id)
    y_ret = ds.ret5[idx]
    y = (y_ret > 0).astype(int)
    r5 = ds.X[idx, R5_COL]
    vol20 = ds.X[idx, VOL20_COL]
    rank = ds.rank[idx]
    p0 = np.concatenate(p0_rows)
    q_all = np.hstack(quant)

    direction = {}
    probs = {}
    for name, chunks in p_by_model.items():
        probs[name] = np.concatenate(chunks)
        direction[name] = _direction_report(y, probs[name], p0, r5, rank)
    best = max(direction, key=lambda n: direction[n]["auc"])

    fold_accuracy = [
        round(float(np.mean((probs[best][fold == k] > 0.5) == (y[fold == k] == 1))), 3)
        for k in np.unique(fold)
    ]

    mkt_r5 = ds.X[idx, FEATURES.index("mkt_r5")]
    mkt_r20 = ds.X[idx, FEATURES.index("mkt_r20")]
    up = y == 1
    diagnostics = {
        "predicted_up_share": round(float(np.mean(probs[best] > 0.5)), 3),
        "baseline_accuracy": {
            "always_up": round(float(up.mean()), 4),
            "always_down_hindsight": round(float(1 - up.mean()), 4),
            "own_momentum_r5": round(float(np.mean((r5 > 0) == up)), 4),
            "market_momentum_r5": round(float(np.mean((mkt_r5 > 0) == up)), 4),
            "market_momentum_r20": round(float(np.mean((mkt_r20 > 0) == up)), 4),
        },
    }

    kind = ds.kind[idx]
    inst = ds.inst_id[idx]
    by_kind = {
        name: _kind_report(kind == code, y, y_ret, probs[best], r5, rank, inst, q_all, vol20)
        for name, code in KIND_CODE.items()
        if np.any(kind == code)
    }

    return {
        "data": {
            "instruments": int(len(np.unique(ds.inst_id))),
            "instruments_by_kind": {
                name: int(len(np.unique(ds.inst_id[ds.kind == code]))) for name, code in KIND_CODE.items()
            },
            "skipped_by_kind": ds.skipped,
            "rows_total": int(len(ds.ret5)),
            "test_rows": int(len(idx)),
            "test_period": [str(ds.unique_dates[int(rank.min())]), str(ds.unique_dates[int(rank.max())])],
            "horizon_sessions": HORIZON,
            "up_rate_in_test": round(float(y.mean()), 4),
        },
        "direction": direction,
        "best_direction_model": best,
        "best_model_accuracy_per_fold": fold_accuracy,
        "by_kind_best_model": by_kind,
        "diagnostics": diagnostics,
        "cross_sectional_ic_best_model": _daily_ic(probs[best], y_ret, rank),
        "abstention_best_model": _abstention_table(y, probs[best], r5),
        "interval_80": _interval_report(y_ret, q_all, vol20, fold),
    }
