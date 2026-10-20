"""Degradation model: point RUL plus a distribution-free 90% interval.

Point RUL comes from gradient boosting on rolling sensor features. The
interval comes from conformalised quantile regression (Romano, Patterson &
Candes, 2019): two quantile models give a first guess, and a held-out
calibration set measures how wrong that guess is, so the final interval has
>= 90% coverage without assuming anything about the error distribution, and
is narrow where the sensors are informative (late life) and wide where they
are not (early life).

Units: RUL is predicted in *cycles* (sorties). It becomes *days* only when
divided by the tail's planned utilisation in sorties per day.
"""

from __future__ import annotations

import hashlib
import math
import pickle
import warnings
from dataclasses import dataclass

import numpy as np
import sklearn
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config
from .data import DegradationSet, Unit

MODEL_VERSION = "prognosis-v1"
WINDOWS = (10, 30)
N_REGIMES = 6
TRAIN_STRIDE = 4  # train on every 4th cycle of each training unit
EVAL_CUTS_PER_UNIT = 12


class Normaliser:
    """Removes the operating-regime effect from sensors (the standard C-MAPSS step).

    Regimes are found by k-means on the operating settings of training units;
    each sensor is then z-scored within its regime.
    """

    def fit(self, units: list[Unit], seed: int) -> "Normaliser":
        ops = np.vstack([u.ops for u in units])
        rng = np.random.default_rng([seed, 3])
        sample = ops[rng.choice(len(ops), size=min(len(ops), 40_000), replace=False)]
        self.op_mean = sample.mean(axis=0)
        self.op_std = np.where(sample.std(axis=0) > 1e-9, sample.std(axis=0), 1.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.km = KMeans(n_clusters=N_REGIMES, n_init=10, random_state=seed).fit(
                (sample - self.op_mean) / self.op_std
            )
        sens = np.vstack([u.sensors for u in units])
        reg = self._regime(ops)
        m = sens.shape[1]
        self.mu = np.zeros((N_REGIMES, m))
        self.sd = np.ones((N_REGIMES, m))
        for r in range(N_REGIMES):
            rows = sens[reg == r]
            if len(rows) > 1:
                self.mu[r] = rows.mean(axis=0)
                sd = rows.std(axis=0)
                self.sd[r] = np.where(sd > 1e-9, sd, 1.0)
        return self

    def _regime(self, ops: np.ndarray) -> np.ndarray:
        return self.km.predict((ops - self.op_mean) / self.op_std)

    def transform(self, unit: Unit) -> np.ndarray:
        reg = self._regime(unit.ops)
        return (unit.sensors - self.mu[reg]) / self.sd[reg]


def _window_stats(z: np.ndarray, cuts: np.ndarray, w: int) -> list[np.ndarray]:
    """Trailing-window mean, std and least-squares slope per sensor at each cut.

    A cut c means "cycles 1..c have been observed". Uses cumulative sums so
    every cut costs O(sensors) regardless of window length.
    """
    n, m = z.shape
    zero = np.zeros((1, m))
    t = np.arange(1, n + 1, dtype=float)[:, None]
    S = np.vstack([zero, np.cumsum(z, axis=0)])
    S2 = np.vstack([zero, np.cumsum(z * z, axis=0)])
    TZ = np.vstack([zero, np.cumsum(t * z, axis=0)])
    lo = np.maximum(cuts - w, 0)
    k = (cuts - lo).astype(float)[:, None]
    s, s2, tz = S[cuts] - S[lo], S2[cuts] - S2[lo], TZ[cuts] - TZ[lo]
    mean = s / k
    std = np.sqrt(np.maximum(s2 / k - mean * mean, 0.0))
    tbar = ((lo + 1 + cuts) / 2.0)[:, None]
    stt = k * (k * k - 1.0) / 12.0
    slope = np.where(stt > 0, (tz - tbar * s) / np.where(stt > 0, stt, 1.0), 0.0)
    return [mean, std, slope]


@dataclass
class Interval:
    point: float  # cycles
    lo: float  # cycles
    hi: float  # cycles


class Prognosis:
    """Trained degradation model with its conformal calibration."""

    def __init__(self, part_numbers: list[str], seed: int, alpha: float = config.CONFORMAL_ALPHA):
        self.part_index = {pn: i for i, pn in enumerate(sorted(part_numbers))}
        self.seed = seed
        self.alpha = alpha
        self.cap: float | None = None

    # ---- features -------------------------------------------------------
    def features(self, unit: Unit, cuts: np.ndarray) -> np.ndarray:
        """Feature matrix at the given cuts: rolling stats per sensor, age (cycles), part code."""
        z = self.norm.transform(unit)
        cols = []
        for w in WINDOWS:
            cols.extend(_window_stats(z, cuts, w))
        age = cuts.astype(float)[:, None]
        part = np.full((len(cuts), 1), self.part_index[unit.part_number], dtype=float)
        return np.hstack([*cols, age, part])

    def _train_rows(self, units: list[Unit]):
        X, y = [], []
        for u in units:
            cuts = np.arange(3, u.life_cycles + 1, TRAIN_STRIDE)
            X.append(self.features(u, cuts))
            y.append(u.life_cycles - cuts)
        return np.vstack(X), np.concatenate(y).astype(float)

    def eval_rows(self, units: list[Unit], tag: int):
        """Random cuts per held-out unit -- drawn the same way for calibration and test."""
        X, y, uid = [], [], []
        for u in units:
            rng = np.random.default_rng([self.seed, tag, int(hashlib.md5(u.unit_id.encode()).hexdigest()[:8], 16)])
            cuts = np.sort(rng.integers(3, u.life_cycles + 1, size=EVAL_CUTS_PER_UNIT))
            X.append(self.features(u, cuts))
            y.append(u.life_cycles - cuts)
            uid.extend([u.unit_id] * len(cuts))
        return np.vstack(X), np.concatenate(y).astype(float), uid

    def _hgb(self, **kw) -> HistGradientBoostingRegressor:
        n_feat = len(WINDOWS) * 3 * self.n_sensors + 2
        return HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=20,
            l2_regularization=1.0, early_stopping=False, random_state=self.seed,
            categorical_features=[n_feat - 1], **kw,
        )

    # ---- fit --------------------------------------------------------------
    def fit(self, deg: DegradationSet, cap: float | None = None,
            train_units: list[Unit] | None = None) -> "Prognosis":
        """Train point + quantile models and calibrate.

        `cap` trains on min(RUL, cap) -- the piecewise-linear target used in most
        C-MAPSS papers. FLIGHTLINE's own model is uncapped; the capped variant
        exists only so metrics.py can show what that convention costs.
        """
        train = train_units if train_units is not None else deg.split("train")
        self.n_sensors = train[0].sensors.shape[1]
        self.cap = cap
        self.norm = Normaliser().fit(train, self.seed)
        X, y = self._train_rows(train)
        if cap is not None:
            y = np.minimum(y, cap)
        self.point = self._hgb(loss="squared_error").fit(X, y)
        self.q_lo = self._hgb(loss="quantile", quantile=self.alpha / 2).fit(X, y)
        self.q_hi = self._hgb(loss="quantile", quantile=1 - self.alpha / 2).fit(X, y)
        Xc, yc, _ = self.eval_rows(deg.split("calibration"), tag=11)
        if cap is not None:
            yc = np.minimum(yc, cap)
        self._calibrate(Xc, yc)
        self.n_calibration = len(yc)
        return self

    def _calibrate(self, Xc: np.ndarray, yc: np.ndarray) -> None:
        # Mondrian CQR. The CQR score is how far the true RUL falls outside the
        # raw quantile band (negative when inside); its ceil((n+1)(1-alpha))-th
        # smallest value is the finite-sample-valid correction for a (1-alpha)
        # interval. One correction for the whole population would let early-life
        # slack hide under-coverage near failure -- exactly where a wrong
        # interval grounds an aircraft -- so calibrate separately within bands
        # of predicted RUL. Coverage then holds within each band, not just on
        # average. Band edges are tertiles of the calibration predictions.
        point = self.point.predict(Xc)
        self.bin_edges = np.quantile(point, [1 / 3, 2 / 3])
        bins = np.searchsorted(self.bin_edges, point)
        lo, hi = self._raw_band(Xc)
        scores = np.maximum(lo - yc, yc - hi)
        self.qhat = np.zeros(len(self.bin_edges) + 1)
        for b in range(len(self.qhat)):
            sb = np.sort(scores[bins == b])
            n = len(sb)
            k = min(n, math.ceil((n + 1) * (1 - self.alpha)))
            self.qhat[b] = sb[k - 1]

    def _raw_band(self, X: np.ndarray):
        lo, hi = self.q_lo.predict(X), self.q_hi.predict(X)
        return np.minimum(lo, hi), np.maximum(lo, hi)

    # ---- predict ------------------------------------------------------------
    def predict_rows(self, X: np.ndarray):
        """(point, lo, hi) arrays in cycles for a feature matrix."""
        raw_point = self.point.predict(X)
        q = self.qhat[np.searchsorted(self.bin_edges, raw_point)]
        lo, hi = self._raw_band(X)
        lo, hi = np.maximum(lo - q, 0.0), np.maximum(hi + q, 0.0)
        hi = np.maximum(hi, lo)
        point = np.clip(raw_point, lo, hi)
        return point, lo, hi

    def predict_unit(self, unit: Unit) -> Interval:
        """Interval for a unit given everything observed so far (cycles)."""
        n = len(unit.sensors)
        p, lo, hi = self.predict_rows(self.features(unit, np.array([n])))
        return Interval(float(p[0]), float(lo[0]), float(hi[0]))

    def predict_installed(self, deg: DegradationSet, failed: set[tuple[str, str]]) -> dict[tuple[str, str], Interval]:
        """Intervals for every serviceable installed LRU, keyed by (tail, part_number)."""
        keys = [k for k in sorted(deg.installed) if k not in failed]
        X = np.vstack([
            self.features(deg.units[deg.installed[k]], np.array([len(deg.units[deg.installed[k]].sensors)]))
            for k in keys
        ])
        p, lo, hi = self.predict_rows(X)
        return {k: Interval(float(p[i]), float(lo[i]), float(hi[i])) for i, k in enumerate(keys)}

    def evaluate(self, deg: DegradationSet) -> dict:
        """Empirical coverage, mean width (cycles) and RMSE (cycles) on held-out test units."""
        Xt, yt, _ = self.eval_rows(deg.split("test"), tag=13)
        if self.cap is not None:
            yt = np.minimum(yt, self.cap)
        p, lo, hi = self.predict_rows(Xt)
        return {
            "coverage": float(np.mean((yt >= lo) & (yt <= hi))),
            "target_coverage": 1 - self.alpha,
            "mean_width_cycles": float(np.mean(hi - lo)),
            "rmse_cycles": float(np.sqrt(np.mean((p - yt) ** 2))),
            "n_test_points": int(len(yt)),
            "n_calibration_points": int(self.n_calibration),
            "conformal_band_edges_cycles": [float(e) for e in self.bin_edges],
            "conformal_corrections_cycles": [float(q) for q in self.qhat],
        }


def decision_window(lead_time_days: float, spares_delay_days: float, depot_queue_days: float,
                    bay_days: float) -> float:
    """Days between ordering a spare and having the aircraft serviceable again.

    = spares lead time + scenario delay + current depot queue + time in the bay.
    A warning is actionable only if it arrives at least this many days before failure.
    """
    return float(lead_time_days + spares_delay_days + depot_queue_days + bay_days)


def assess(iv: Interval, cycles_per_day: float, window_days: float) -> dict:
    """Convert an interval to days and apply the abstention gate.

    Abstain when the interval is wider than the decision window *and* its lower
    edge reaches into that window: the model cannot tell "order today" from
    "no action yet", so it says so and recommends inspection. An LRU whose
    whole interval sits beyond the window needs no decision today and is
    simply monitored, however wide its interval.
    """
    u = max(cycles_per_day, 1e-6)
    lo, hi, point = iv.lo / u, iv.hi / u, iv.point / u
    width = hi - lo
    reaches_window = lo <= window_days
    abstain = bool(width > window_days and reaches_window)
    if abstain:
        status = "inspect"
    elif reaches_window:
        status = "order_now"
    else:
        status = "monitor"
    return {
        "rul_point": point, "rul_lo": lo, "rul_hi": hi,
        "rul_point_cycles": iv.point, "rul_lo_cycles": iv.lo, "rul_hi_cycles": iv.hi,
        "interval_width_days": width, "decision_window_days": window_days,
        "abstain": abstain, "status": status,
    }


def fingerprint(deg: DegradationSet) -> str:
    h = hashlib.sha256()
    h.update(f"{MODEL_VERSION}|{sklearn.__version__}|{deg.source}|{config.SEED}|{config.CONFORMAL_ALPHA}".encode())
    for uid in sorted(deg.units):
        u = deg.units[uid]
        h.update(f"{uid}:{u.split}:{u.life_cycles}:{len(u.sensors)}:{float(u.sensors.sum()):.6f}".encode())
    return h.hexdigest()


def load_or_train(deg: DegradationSet, part_numbers: list[str]) -> tuple[Prognosis, bool]:
    """Return the cached model if it matches this data, else train and cache. (model, was_cached)."""
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = config.MODEL_DIR / "prognosis.pkl"
    fp = fingerprint(deg)
    if path.exists():
        try:
            with path.open("rb") as f:
                blob = pickle.load(f)
            if blob.get("fingerprint") == fp:
                return blob["model"], True
        except Exception:
            pass
    model = Prognosis(part_numbers, seed=config.SEED).fit(deg)
    with path.open("wb") as f:
        pickle.dump({"fingerprint": fp, "model": model}, f)
    return model, False


def predict(tail: str, lru: str) -> dict:
    """{rul_point, rul_lo, rul_hi (days), abstain, ...} for one installed LRU under the current scenario.

    `lru` is the part number fitted to `tail`.
    """
    from . import engine

    return engine.current().predict(tail, lru)
