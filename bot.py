import logging
import asyncio
import time
import os
from datetime import datetime
import config
from signal_engine import SignalEngine
from martingale import MartingaleManager
from polymarket import PolymarketManager
from dashboard import Dashboard
from web_server import WebServer
from price_fetcher import PriceFetcher

# Setup logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class PolymarketBot:
    """
    Main trading bot orchestrator:
    1. Monitor Binance 1m candles
    2. Generate UP/DOWN signals (RSI + MACD + EMA + sentiment)
    3. Detect 5-minute Polymarket windows
    4. Enter at T-240s with high-confidence signals
    5. Manage Martingale staking
    """

    def __init__(self):
        logger.info("=" * 60)
        logger.info("🤖 Polymarket BTC 5-Min Trading Bot Starting...")
        logger.info("=" * 60)

        # Validate configuration
        try:
            config.validate_config()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise

        # Initialize components
        self.signal_engine = SignalEngine()
        self.martingale = MartingaleManager()
        self.polymarket = PolymarketManager()
        self.dashboard = Dashboard(self)
        self.web_server = WebServer(self)
        self.price_fetcher = PriceFetcher()

        # State
        self.running = False
        self.current_window_start = None
        self.last_signal = None
        self.pending_order = None

        logger.info("✅ Bot initialized successfully")

    async def fetch_price_data(self):
        """Fetch BTC price & chart data from CoinGecko (free, no API key needed)."""
        logger.info("📊 Fetching BTC price data from CoinGecko API...")

        try:
            # Initial fetch
            data = self.price_fetcher.refresh()

            logger.info(f"✅ BTC Current Price: ${data['current_price']:,.2f}")
            logger.info(f"✅ Loaded {len(data['candles'])} candles from CoinGecko")

            # Add candles to signal engine & dashboard
            for candle in data['candles']:
                self.signal_engine.add_candle(candle)
                self.web_server.add_candle(candle)

            # Periodic refresh every 60 seconds (CoinGecko updates ~every 60s)
            while self.running:
                await asyncio.sleep(60)

                data = self.price_fetcher.refresh()

                # Add new candles
                for candle in data['candles']:
                    self.signal_engine.add_candle(candle)
                    self.web_server.add_candle(candle)

                logger.debug(f"Price update: ${data['current_price']:,.2f}")

        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            await asyncio.sleep(10)

    def get_current_window_seconds(self) -> int:
        """
        Calculate seconds since start of current 5-minute window.
        Polymarket windows reset at :00, :05, :10, etc.
        """
        now = datetime.now()
        seconds_in_hour = now.minute * 60 + now.second

        # Which 5-min window are we in?
        window_position = seconds_in_hour % 300  # 0-299 seconds
        return window_position

    def get_window_countdown(self) -> int:
        """Seconds until next window closes."""
        return 300 - self.get_current_window_seconds()

    async def check_and_enter(self):
        """
        Check if conditions are met to enter a trade:
        - In the entry window (T-240s, i.e., last 60 seconds)
        - Signal score > MIN_SIGNAL_SCORE
        - Current market available
        """
        window_seconds = self.get_current_window_seconds()
        countdown = self.get_window_countdown()

        # Only check during entry window (last 60 seconds: 240-300s)
        if window_seconds < config.ENTRY_WINDOW_START:
            return

        # Avoid duplicate entries in same window
        if self.pending_order:
            logger.debug(f"Order pending, skipping entry ({countdown}s to window close)")
            return

        # Generate signal
        market = self.polymarket.get_current_market()
        if not market:
            logger.warning("No current market available")
            return

        orderbook = self.polymarket.get_order_book(market.get('condition_id'))
        signal = self.signal_engine.calculate_signal(
            bid_volume=orderbook['bid_volume'],
            ask_volume=orderbook['ask_volume'],
        )

        self.last_signal = signal

        # Check if should enter
        if not self.signal_engine.should_enter(signal):
            logger.debug(f"Signal too weak: {signal['score']:.1f} (need {config.MIN_SIGNAL_SCORE}), skipping")
            return

        # Get next stake
        stake = self.martingale.get_next_stake()

        # Check balance
        balance = self.polymarket.get_balance()
        if balance and balance < stake:
            logger.warning(f"Insufficient balance: ${balance:.2f} < ${stake:.2f}")
            return

        # Place order
        await self.place_trade(market, signal, stake)

    async def place_trade(self, market: dict, signal: dict, stake: float):
        """Place a trade on Polymarket."""
        try:
            logger.info(f"🎯 ENTERING {signal['direction']} | Score: {signal['score']:.1f} | Stake: ${stake:.2f}")

            # Get token ID for direction
            token_id = 1 if signal['direction'] == 'UP' else 0

            # Place order
            order_id = self.polymarket.place_order(
                condition_id=market.get('condition_id'),
                token_id=token_id,
                direction=signal['direction'],
                amount=stake,
            )

            if order_id:
                self.pending_order = {
                    'order_id': order_id,
                    'direction': signal['direction'],
                    'stake': stake,
                    'level': self.martingale.current_level,
                    'timestamp': time.time(),
                }
                logger.info(f"✅ Trade placed: {order_id}")
            else:
                logger.error("Failed to place order")

        except Exception as e:
            logger.error(f"Trade placement error: {e}")

    async def monitor_window_close(self):
        """
        Monitor window close and record P&L.
        At T-300s (window reset), check if order won or lost.
        """
        while self.running:
            window_seconds = self.get_current_window_seconds()

            # At window close (0-5 seconds)
            if window_seconds < 5:
                if self.pending_order:
                    await self.settle_trade()

            await asyncio.sleep(1)

    async def settle_trade(self):
        """Check trade outcome and update Martingale state."""
        if not self.pending_order:
            return

        try:
            order_id = self.pending_order['order_id']
            stake = self.pending_order['stake']

            # Get order status
            status = self.polymarket.get_order_status(order_id)

            if not status:
                logger.warning(f"Could not determine outcome for {order_id}")
                self.pending_order = None
                return

            # Determine if order won (token price > 0.50 at close) or lost
            # This depends on actual Polymarket settlement price
            final_price = status.get('final_price', 0.5)

            if final_price > 0.5:
                # Token went UP
                is_win = self.pending_order['direction'] == 'UP'
            else:
                # Token went DOWN
                is_win = self.pending_order['direction'] == 'DOWN'

            if is_win:
                # Approximate win: made ~50% on stake (minus fees)
                pnl = stake * 0.45
                self.martingale.record_win(stake, pnl)
                logger.info(f"🎉 WIN | P&L: +${pnl:.2f}")
            else:
                # Loss: lost the stake
                self.martingale.record_loss(stake, stake)
                logger.info(f"💔 LOSS | Lost: ${stake:.2f}")

            self.pending_order = None

        except Exception as e:
            logger.error(f"Settlement error: {e}")
            self.pending_order = None

    async def main_loop(self):
        """Main bot loop."""
        logger.info("🚀 Starting main loop...")

        # Start concurrent tasks (web dashboard runs in background, no terminal display)
        await asyncio.gather(
            self.fetch_price_data(),
            self.monitor_window_close(),
        )

    async def start(self):
        """Start the bot."""
        self.running = True

        try:
            # Start web server in background
            port = int(os.getenv('PORT', 8000))
            logger.info(f"🌐 Dashboard running on http://0.0.0.0:{port}")
            logger.info(f"🌐 Access it at: http://127.0.0.1:{port}")
            self.web_server.run_async(port=port)

            await self.main_loop()
        except KeyboardInterrupt:
            logger.info("\n⏸️  Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot."""
        self.running = False
        logger.info("🛑 Bot shutting down...")

        logger.info("=" * 60)
        logger.info("👋 Bot stopped")
        logger.info("=" * 60)


async def main():
    """Entry point."""
    bot = PolymarketBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
