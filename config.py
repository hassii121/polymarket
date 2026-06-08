import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from enum import Enum

# Load environment variables
load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent

# Logger for config messages
logger = logging.getLogger(__name__)


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


# ==================== GENERAL ====================
ENVIRONMENT = Environment(os.getenv("ENVIRONMENT", "development"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG = ENVIRONMENT == Environment.DEVELOPMENT


# ==================== POLYMARKET API ====================
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
POLYMARKET_CHAIN_ID = int(os.getenv("POLYMARKET_CHAIN_ID", 137))  # Polygon mainnet
POLYMARKET_RPC_URL = os.getenv("POLYMARKET_RPC_URL", "https://polygon-rpc.com")

# Polymarket CLOB constants
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_ORDER_BOOK_URL = "https://clob.polymarket.com/book"


# ==================== COINGECKO API (Free BTC Price Feed) ====================
COINGECKO_API = "https://api.coingecko.com/api/v3"
BTC_PRICE_ENDPOINT = f"{COINGECKO_API}/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true"
BTC_CHART_ENDPOINT = f"{COINGECKO_API}/coins/bitcoin/ohlc?vs_currency=usd&days=1"  # Last 24h, 1m candles

logger.info("✅ Using CoinGecko API for BTC price & chart (FREE, NO KEY NEEDED)")


# ==================== TRADING CONFIGURATION ====================
BASE_STAKE = float(os.getenv("BASE_STAKE", 2.0))
MAX_MARTINGALE_LEVEL = int(os.getenv("MAX_MARTINGALE_LEVEL", 5))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 70))

# Martingale stake levels: [level1, level2, level3, level4, level5]
MARTINGALE_STAKES = [
    BASE_STAKE,
    BASE_STAKE * 2,
    BASE_STAKE * 4,
    BASE_STAKE * 8,
    BASE_STAKE * 16,
]

# Window timing (5-minute Polymarket windows)
WINDOW_DURATION_SECONDS = 300  # 5 minutes
ENTRY_WINDOW_START = 240  # Enter 240 seconds before window closes (4 min mark)


# ==================== SIGNAL ENGINE WEIGHTS ====================
SIGNAL_WEIGHTS = {
    "ta": 0.40,              # RSI + MACD + EMA weight
    "funding_rate": 0.30,    # Funding rate extremes weight
    "fear_greed": 0.20,      # Fear & Greed Index weight
    "orderbook": 0.10,       # Order book imbalance weight
}

# Technical Analysis parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_PERIOD = 9

# Fear & Greed thresholds
FEAR_GREED_EXTREME_LOW = 25  # Extreme fear
FEAR_GREED_EXTREME_HIGH = 75  # Extreme greed

# Funding rate thresholds
FUNDING_RATE_EXTREME = 0.0010  # |funding_rate| > 0.001 is extreme


# ==================== EXTERNAL APIs ====================
FEAR_GREED_API = "https://api.alternative.me/fng/?limit=1"
BYBIT_FUNDING_API = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"

# Request timeout (seconds)
API_TIMEOUT = 10


# ==================== WALLET & SIGNING ====================
SETTLEMENT_CURRENCY = "USDC"
SETTLEMENT_CHAIN = "Polygon"

# For Trust Wallet / Polygon signing
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")


# ==================== LOGGING & STORAGE ====================
LOG_DIR = PROJECT_ROOT / "logs"
STATE_DIR = PROJECT_ROOT / "state"
TRADES_FILE = PROJECT_ROOT / "trades.json"

# Create directories if they don't exist
LOG_DIR.mkdir(exist_ok=True)
STATE_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "bot.log"


# ==================== RAILWAY DEPLOYMENT ====================
PORT = int(os.getenv("PORT", 8000))
PYTHON_VERSION = os.getenv("PYTHON_VERSION", "3.11")


def validate_config():
    """Validate that all required config values are set."""
    errors = []

    if ENVIRONMENT == Environment.PRODUCTION:
        if not POLYMARKET_PRIVATE_KEY:
            errors.append("POLYMARKET_PRIVATE_KEY is required in production")

    if errors:
        print("Configuration Errors:")
        for error in errors:
            print(f"  ❌ {error}")
        raise ValueError("Missing required configuration")

    print("✅ Configuration validated")
    return True
