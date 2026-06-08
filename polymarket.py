import logging
from typing import Dict, Optional, List
import requests
import config

logger = logging.getLogger(__name__)

# Optional imports for trading (not needed for dashboard)
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import Order
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    logger.warning("py_clob_client not installed - trading disabled (dashboard only)")


class PolymarketManager:
    """
    Manages Polymarket CLOB API interactions:
    - Connect to Polygon wallet
    - Get BTC 5-min markets
    - Place orders (UP/DOWN)
    - Check order status
    """

    def __init__(self):
        if not CLOB_AVAILABLE:
            logger.info("⚠️  CLOB client unavailable - dashboard mode only")
            self.client = None
            return

        try:
            # Initialize CLOB client
            self.client = ClobClient(
                private_key=config.POLYMARKET_PRIVATE_KEY,
                chain_id=config.POLYMARKET_CHAIN_ID,
            )
            logger.info("✅ Polymarket CLOB client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CLOB client: {e}")
            self.client = None

    def get_btc_5min_markets(self) -> List[Dict]:
        """
        Fetch all BTC 5-minute Up/Down binary markets from Polymarket.
        Returns list of active markets.
        """
        try:
            # Get order book to find BTC 5-min markets
            markets = []

            # This is a placeholder - actual implementation would
            # query Polymarket API for current 5-min BTC markets
            # Markets change every 5 minutes, so we need live data

            logger.debug(f"Found {len(markets)} BTC 5-min markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch BTC markets: {e}")
            return []

    def get_current_market(self) -> Optional[Dict]:
        """
        Get the current active BTC 5-min market window.
        Markets typically have condition_id and token_ids for UP/DOWN.
        """
        try:
            markets = self.get_btc_5min_markets()

            if not markets:
                logger.warning("No BTC 5-min markets found")
                return None

            # Return the first active market (most recent window)
            current_market = markets[0]
            logger.info(f"Current market: {current_market.get('condition_id')}")

            return current_market

        except Exception as e:
            logger.error(f"Failed to get current market: {e}")
            return None

    def get_order_book(self, condition_id: str) -> Dict:
        """
        Get order book (bid/ask spread) for a condition.
        Used to calculate order book imbalance for signal.
        """
        try:
            resp = requests.get(
                f"{config.POLYMARKET_ORDER_BOOK_URL}/{condition_id}",
                timeout=config.API_TIMEOUT
            )
            data = resp.json()

            # Extract bid/ask volumes
            bids = [order for order in data.get('bids', []) if float(order.get('price', 0)) >= 0.45]
            asks = [order for order in data.get('asks', []) if float(order.get('price', 0)) <= 0.55]

            bid_volume = sum(float(o.get('size', 0)) for o in bids)
            ask_volume = sum(float(o.get('size', 0)) for o in asks)

            logger.debug(f"Order book: Bids={bid_volume:.2f}, Asks={ask_volume:.2f}")

            return {
                'condition_id': condition_id,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'mid_price': (bids[0].get('price', 0.5) + asks[0].get('price', 0.5)) / 2 if bids and asks else 0.5,
            }

        except Exception as e:
            logger.error(f"Failed to get order book for {condition_id}: {e}")
            return {'bid_volume': 0, 'ask_volume': 0, 'mid_price': 0.5}

    def place_order(self, condition_id: str, token_id: str, direction: str, amount: float) -> Optional[str]:
        """
        Place an order on Polymarket.

        Args:
            condition_id: Market condition ID
            token_id: Token ID (0=NO/DOWN, 1=YES/UP)
            direction: 'UP' or 'DOWN'
            amount: USDC amount to stake

        Returns:
            Order ID if successful, None otherwise
        """
        if not self.client:
            logger.error("CLOB client not initialized")
            return None

        try:
            # Determine token to trade
            # token_id: 0 = NO (DOWN), 1 = YES (UP)
            token = 1 if direction == 'UP' else 0

            # Create order
            order = Order(
                token_id=token,
                price=0.5,  # Enter at mid (0.50), adjust based on signal strength
                size=amount,
                side='BUY',
            )

            # Send order
            response = self.client.create_order(order)
            order_id = response.get('orderId')

            if order_id:
                logger.info(f"✅ Order placed: {direction} ${amount:.2f} | Order ID: {order_id}")
                return order_id
            else:
                logger.error(f"Order response missing ID: {response}")
                return None

        except Exception as e:
            logger.error(f"Failed to place {direction} order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self.client:
            return False

        try:
            self.client.cancel_order(order_id)
            logger.info(f"✅ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of an order."""
        if not self.client:
            return None

        try:
            status = self.client.get_order(order_id)
            return status
        except Exception as e:
            logger.error(f"Failed to get order status {order_id}: {e}")
            return None

    def get_balance(self) -> Optional[float]:
        """Get USDC balance in wallet."""
        if not self.client:
            return None

        try:
            # Get account balance - implementation depends on py-clob-client
            balance = self.client.get_balance()
            logger.debug(f"Wallet balance: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if CLOB client is properly initialized."""
        return self.client is not None
