"""Runtime config for the automated trader — a small JSON file in the data dir.

Editable from the UI. Everything the live loop needs to know: what to watch, on
what timeframe, which strategy roster is active, the turnover throttles, and
whether the bot auto-arms on launch. Paper-only; there is no live-money setting
here on purpose.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_NAME = "keel_config.json"

DEFAULT_WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
]


@dataclass
class Config:
    # Universe mode (default): scan the whole tradable market and let the scanner
    # pick candidates. `watchlist` is only used when universe is False.
    universe: bool = True
    watchlist: list[str] = field(default_factory=lambda: list(DEFAULT_WATCHLIST))
    strategy: str = "auto"  # "auto" = the meta-brain selects per symbol per moment
    timeframe: str = "5Min"
    max_positions: int = 8
    max_new_per_day: int = 30
    risk_fraction: float = 0.01
    poll_seconds: int = 60
    scan_seconds: int = 300  # how often to re-scan the whole market
    top_n: int = 40  # candidates carried from the scan into the trader
    min_price: float = 3.0
    min_dollar_volume: float = 5_000_000.0
    autostart_armed: bool = True  # paper only — arms the paper loop on launch
    feed: str = "iex"

    def clamp(self) -> Config:
        # Risk fraction is a guarded constant range; nothing can push it wild.
        self.risk_fraction = min(0.02, max(0.0025, float(self.risk_fraction)))
        self.max_positions = max(1, int(self.max_positions))
        self.max_new_per_day = max(1, int(self.max_new_per_day))
        self.poll_seconds = max(15, int(self.poll_seconds))
        self.scan_seconds = max(60, int(self.scan_seconds))
        self.top_n = max(5, min(200, int(self.top_n)))
        self.watchlist = [s.strip().upper() for s in self.watchlist if s.strip()]
        return self


def config_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / CONFIG_NAME


def load_config(data_dir: str | Path) -> Config:
    p = config_path(data_dir)
    if p.is_file():
        raw = json.loads(p.read_text(encoding="utf-8"))
        known = {k: raw[k] for k in raw if k in Config.__dataclass_fields__}
        return Config(**known).clamp()
    return Config()


def save_config(data_dir: str | Path, cfg: Config) -> Path:
    p = config_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg.clamp()), indent=2), encoding="utf-8")
    return p
