import logging
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import requests
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
import config

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Generates UP/DOWN signals using:
    - RSI + MACD + EMA (40% weight)
    - Funding rate extremes (30% weight)
    - Fear & Greed Index (20% weight)
    - Order book imbalance (10% weight)
    """

    def __init__(self):
        self.candles = []  # Store 1m candles for TA
        self.fear_greed_cache = None
        self.funding_rate_cache = None

    def add_candle(self, candle: Dict) -> None:
        """Add a new 1-minute candle to the buffer."""
        open_val = candle.get('open') or candle.get('o')
        high_val = candle.get('high') or candle.get('h')
        low_val = candle.get('low') or candle.get('l')
        close_val = candle.get('close') or candle.get('c')
        volume_val = candle.get('volume') or candle.get('v') or 0

        if open_val and high_val and low_val and close_val:
            self.candles.append({
                'timestamp': candle.get('timestamp') or candle.get('t'),
                'open': float(open_val),
                'high': float(high_val),
                'low': float(low_val),
                'close': float(close_val),
                'volume': float(volume_val),
            })

        # Keep only last 100 candles (enough for MACD/RSI/EMA)
        if len(self.candles) > 100:
            self.candles = self.candles[-100:]

    def _prepare_dataframe(self) -> Optional[pd.DataFrame]:
        """Convert candles to DataFrame for TA calculations."""
        if len(self.candles) < max(config.RSI_PERIOD, config.MACD_SLOW, config.EMA_PERIOD):
            return None

        df = pd.DataFrame(self.candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df.sort_values('timestamp').reset_index(drop=True)

    def calculate_ta_score(self) -> Optional[float]:
        """
        Calculate technical analysis score (0-100) based on:
        - RSI: 30-70 neutral, <30 bullish, >70 bearish
        - MACD: positive = bullish, negative = bearish
        - EMA: price above EMA = bullish, below = bearish
        """
        df = self._prepare_dataframe()
        if df is None or len(df) < config.MACD_SLOW:
            return None

        # RSI calculation
        rsi = RSIIndicator(df['close'], window=config.RSI_PERIOD).rsi()
        rsi_latest = rsi.iloc[-1]

        # RSI score: 0 at 70 (overbought), 100 at 30 (oversold), 50 neutral
        if rsi_latest < 30:
            rsi_score = 75  # Strong oversold (bullish)
        elif rsi_latest > 70:
            rsi_score = 25  # Strong overbought (bearish)
        else:
            rsi_score = 50 + (50 - rsi_latest) / 2  # Neutral zone

        # MACD calculation
        macd = MACD(df['close'], window_fast=config.MACD_FAST,
                    window_slow=config.MACD_SLOW, window_sign=config.MACD_SIGNAL)
        macd_diff = macd.macd_diff().iloc[-1]

        # MACD score: positive = bullish (up to 100), negative = bearish (down to 0)
        macd_score = 50 + min(50, max(-50, macd_diff * 1000))

        # EMA calculation
        ema = EMAIndicator(df['close'], window=config.EMA_PERIOD).ema_indicator()
        price_latest = df['close'].iloc[-1]
        ema_latest = ema.iloc[-1]

        # EMA score: above EMA = bullish, below = bearish
        if price_latest > ema_latest:
            ema_score = 60  # Price above EMA (bullish)
        else:
            ema_score = 40  # Price below EMA (bearish)

        # Composite TA score (simple average)
        ta_score = (rsi_score + macd_score + ema_score) / 3

        logger.debug(f"TA Score: RSI={rsi_score:.1f}, MACD={macd_score:.1f}, EMA={ema_score:.1f}, Total={ta_score:.1f}")
        return ta_score

    def fetch_fear_greed(self) -> Optional[int]:
        """Fetch Fear & Greed Index (0-100, 0=extreme fear, 100=extreme greed)."""
        try:
            resp = requests.get(config.FEAR_GREED_API, timeout=config.API_TIMEOUT)
            data = resp.json()
            fng_value = int(data['data'][0]['value'])
            self.fear_greed_cache = fng_value
            return fng_value
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed: {e}")
            return self.fear_greed_cache

    def calculate_fear_greed_score(self) -> Optional[float]:
        """
        Convert Fear & Greed to signal score (0-100):
        - < 25: Extreme fear (bullish) → high score
        - 25-75: Neutral
        - > 75: Extreme greed (bearish) → low score
        """
        fng = self.fetch_fear_greed()
        if fng is None:
            return 50  # Default neutral

        if fng < config.FEAR_GREED_EXTREME_LOW:
            score = 80  # Extreme fear = strong bullish
        elif fng > config.FEAR_GREED_EXTREME_HIGH:
            score = 20  # Extreme greed = strong bearish
        else:
            score = 50 + (50 - fng) / 3  # Smooth interpolation

        logger.debug(f"Fear & Greed: {fng} → Score: {score:.1f}")
        return score

    def fetch_funding_rate(self) -> Optional[float]:
        """Fetch BTC funding rate from Bybit."""
        try:
            resp = requests.get(config.BYBIT_FUNDING_API, timeout=config.API_TIMEOUT)
            data = resp.json()
            ticker = [t for t in data['result']['list'] if t['symbol'] == 'BTCUSDT'][0]
            funding_rate = float(ticker['fundingRate'])
            self.funding_rate_cache = funding_rate
            return funding_rate
        except Exception as e:
            logger.warning(f"Failed to fetch funding rate: {e}")
            return self.funding_rate_cache

    def calculate_funding_rate_score(self) -> Optional[float]:
        """
        Convert funding rate to signal score (0-100):
        - Positive & extreme: Bullish sentiment (overheated) → low score
        - Negative & extreme: Bearish sentiment (capitulation) → high score
        - Neutral: 50
        """
        fr = self.fetch_funding_rate()
        if fr is None:
            return 50  # Default neutral

        if abs(fr) < config.FUNDING_RATE_EXTREME:
            score = 50  # Neutral funding
        elif fr > config.FUNDING_RATE_EXTREME:
            score = 25  # Extreme positive (overheated, bearish)
        else:  # fr < -FUNDING_RATE_EXTREME
            score = 75  # Extreme negative (capitulation, bullish)

        logger.debug(f"Funding Rate: {fr:.6f} → Score: {score:.1f}")
        return score

    def calculate_orderbook_score(self, bid_volume: float, ask_volume: float) -> float:
        """
        Calculate order book imbalance score (0-100):
        - More bids = bullish → high score
        - More asks = bearish → low score
        """
        if bid_volume + ask_volume == 0:
            return 50

        bid_ratio = bid_volume / (bid_volume + ask_volume)

        # Convert ratio (0-1) to score (0-100)
        score = bid_ratio * 100

        logger.debug(f"Order Book: Bid Ratio={bid_ratio:.2%} → Score: {score:.1f}")
        return score

    def calculate_signal(self, bid_volume: float = 0, ask_volume: float = 0) -> Dict:
        """
        Calculate overall signal score (0-100) using weighted components.

        Returns:
            {
                'score': 0-100,
                'direction': 'UP' or 'DOWN' (if score > 50: UP, else DOWN),
                'components': {...},
                'ready': bool (True if enough data)
            }
        """
        ta_score = self.calculate_ta_score()
        fg_score = self.calculate_fear_greed_score()
        fr_score = self.calculate_funding_rate_score()
        ob_score = self.calculate_orderbook_score(bid_volume, ask_volume)

        if ta_score is None:
            return {
                'score': 0,
                'direction': 'UNKNOWN',
                'components': {},
                'ready': False,
                'reason': 'Not enough candles'
            }

        # Weighted average
        total_score = (
            ta_score * config.SIGNAL_WEIGHTS['ta'] +
            fr_score * config.SIGNAL_WEIGHTS['funding_rate'] +
            fg_score * config.SIGNAL_WEIGHTS['fear_greed'] +
            ob_score * config.SIGNAL_WEIGHTS['orderbook']
        )

        direction = 'UP' if total_score >= 50 else 'DOWN'

        result = {
            'score': total_score,
            'direction': direction,
            'components': {
                'ta': ta_score,
                'funding_rate': fr_score,
                'fear_greed': fg_score,
                'orderbook': ob_score,
            },
            'ready': True,
            'confidence': 'HIGH' if abs(total_score - 50) > 20 else 'MEDIUM'
        }

        logger.info(f"Signal: {direction} (Score: {total_score:.1f}, Confidence: {result['confidence']})")
        return result

    def should_enter(self, signal: Dict) -> bool:
        """Check if signal score meets entry threshold."""
        if not signal['ready']:
            return False

        return signal['score'] > config.MIN_SIGNAL_SCORE
