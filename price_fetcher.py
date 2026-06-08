import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)


class PriceFetcher:
    """
    Fetches BTC price & chart data from CoinGecko (free, no API key needed)
    Perfect for getting market direction without Binance dependency
    """

    def __init__(self):
        self.current_price = 0
        self.price_history = []
        self.last_update = None

    def fetch_current_price(self) -> Optional[float]:
        """Get current BTC price in USD."""
        try:
            response = requests.get(config.BTC_PRICE_ENDPOINT, timeout=config.API_TIMEOUT)
            data = response.json()
            price = data['bitcoin']['usd']
            self.current_price = price
            self.last_update = datetime.now()
            logger.debug(f"BTC Price: ${price:,.2f}")
            return price
        except Exception as e:
            logger.error(f"Failed to fetch BTC price: {e}")
            return self.current_price if self.current_price > 0 else None

    def fetch_chart_data(self) -> List[Dict]:
        """
        Get BTC OHLC data for last 24 hours.
        Returns list of [timestamp, open, high, low, close] from CoinGecko
        """
        try:
            response = requests.get(config.BTC_CHART_ENDPOINT, timeout=config.API_TIMEOUT)
            ohlc_data = response.json()

            # CoinGecko returns: [timestamp_ms, open, high, low, close]
            candles = []
            for ohlc in ohlc_data:
                if len(ohlc) >= 5:
                    candles.append({
                        'timestamp': ohlc[0],  # milliseconds
                        'open': float(ohlc[1]),
                        'high': float(ohlc[2]),
                        'low': float(ohlc[3]),
                        'close': float(ohlc[4]),
                        'volume': 0,  # CoinGecko doesn't provide volume in this endpoint
                    })

            self.price_history = candles
            logger.info(f"✅ Fetched {len(candles)} BTC candles from CoinGecko")
            return candles

        except Exception as e:
            logger.error(f"Failed to fetch chart data: {e}")
            return self.price_history

    def get_price_change_24h(self) -> Optional[Dict]:
        """
        Calculate 24h price change from chart data
        Returns: {'change': float, 'change_pct': float, 'direction': 'UP'|'DOWN'}
        """
        if len(self.price_history) < 2:
            return None

        # Get first and last prices
        open_price = self.price_history[0]['open']
        close_price = self.price_history[-1]['close']

        change = close_price - open_price
        change_pct = (change / open_price) * 100

        return {
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'direction': 'UP' if change > 0 else 'DOWN',
            'open': open_price,
            'close': close_price,
        }

    def get_24h_high_low(self) -> Optional[Dict]:
        """Get 24h high and low prices."""
        if not self.price_history:
            return None

        highs = [c['high'] for c in self.price_history]
        lows = [c['low'] for c in self.price_history]

        return {
            'high_24h': max(highs),
            'low_24h': min(lows),
        }

    def refresh(self) -> Dict:
        """Refresh all price data and return current state."""
        self.fetch_current_price()
        self.fetch_chart_data()

        return {
            'current_price': self.current_price,
            'candles': self.price_history,
            'change_24h': self.get_price_change_24h(),
            'high_low_24h': self.get_24h_high_low(),
            'last_update': self.last_update.isoformat() if self.last_update else None,
        }
