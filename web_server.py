import logging
import threading
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from collections import deque

logger = logging.getLogger(__name__)


class WebServer:
    def __init__(self, bot=None):
        self.bot = bot

        # Create Flask app
        self.app = Flask(
            __name__,
            template_folder='templates',
            static_folder='static'
        )
        CORS(self.app)

        # Data storage
        self.candles_1m = deque(maxlen=500)

        # Setup routes
        self._setup_routes()

        logger.info("✅ Flask app created successfully")

    def _setup_routes(self):
        """Setup all routes."""

        @self.app.route('/')
        def index():
            """Serve main dashboard."""
            try:
                return render_template('index.html')
            except Exception as e:
                logger.error(f"Error rendering template: {e}")
                return f"<h1>Error loading dashboard</h1><p>{str(e)}</p>", 500

        @self.app.route('/test')
        def test():
            """Test endpoint."""
            return jsonify({'status': 'Flask is working!', 'bot': 'running'})

        @self.app.route('/api/health')
        def health():
            """Health check."""
            return jsonify({'status': 'ok'})

        @self.app.route('/api/candles')
        def get_candles():
            """Get BTC candles."""
            return jsonify(list(self.candles_1m))

        @self.app.route('/api/stats')
        def get_stats():
            """Get bot stats."""
            if not self.bot:
                return jsonify({
                    'current_level': 1,
                    'current_stake': 2.0,
                    'total_wins': 0,
                    'total_losses': 0,
                    'win_rate': 0,
                    'net_pnl': 0,
                    'total_trades': 0,
                    'signal_score': 0,
                    'signal_direction': 'UNKNOWN',
                    'signal_confidence': 'UNKNOWN',
                })

            stats = self.bot.martingale.get_stats()
            signal = self.bot.last_signal or {}

            return jsonify({
                'current_level': stats.get('current_level', 1),
                'current_stake': stats.get('current_stake', 2.0),
                'total_wins': stats.get('total_wins', 0),
                'total_losses': stats.get('total_losses', 0),
                'win_rate': stats.get('win_rate', 0),
                'net_pnl': stats.get('net_pnl', 0),
                'total_trades': stats.get('total_trades', 0),
                'signal_score': signal.get('score', 0),
                'signal_direction': signal.get('direction', 'UNKNOWN'),
                'signal_confidence': signal.get('confidence', 'UNKNOWN'),
            })

        @self.app.route('/api/window-info')
        def get_window():
            """Get window info."""
            if not self.bot:
                return jsonify({
                    'window_seconds': 0,
                    'countdown': 300,
                    'in_entry_window': False,
                    'percentage': 0,
                })

            window_seconds = self.bot.get_current_window_seconds()
            countdown = self.bot.get_window_countdown()

            return jsonify({
                'window_seconds': window_seconds,
                'countdown': countdown,
                'in_entry_window': window_seconds >= 240,
                'percentage': (window_seconds / 300) * 100,
            })

        @self.app.route('/api/pending-order')
        def get_pending_order():
            """Get pending order."""
            if not self.bot or not self.bot.pending_order:
                return jsonify(None)

            order = self.bot.pending_order
            return jsonify({
                'direction': order.get('direction'),
                'stake': order.get('stake'),
                'level': order.get('level'),
                'order_id': order.get('order_id'),
            })

        @self.app.route('/api/trades')
        def get_trades():
            """Get recent trades."""
            if not self.bot:
                return jsonify([])

            return jsonify(self.bot.martingale.get_history(limit=20))

        @self.app.route('/api/signal-components')
        def get_signal_components():
            """Get signal components."""
            if not self.bot or not self.bot.last_signal:
                return jsonify({
                    'ta': 0,
                    'funding_rate': 0,
                    'fear_greed': 0,
                    'orderbook': 0,
                })

            return jsonify(self.bot.last_signal.get('components', {}))

        @self.app.route('/api/btc/price')
        def get_btc_price():
            """Get BTC price."""
            if not self.bot:
                return jsonify({
                    'current_price': 0,
                    'change_24h': None,
                    'high_low_24h': None,
                })

            return jsonify({
                'current_price': self.bot.price_fetcher.current_price,
                'change_24h': self.bot.price_fetcher.get_price_change_24h(),
                'high_low_24h': self.bot.price_fetcher.get_24h_high_low(),
            })

        # Error handlers
        @self.app.errorhandler(404)
        def not_found(e):
            return jsonify({'error': 'Page not found'}), 404

        @self.app.errorhandler(500)
        def server_error(e):
            logger.error(f"Server error: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    def add_candle(self, candle):
        """Add a candle to storage."""
        self.candles_1m.append({
            'timestamp': candle.get('timestamp', 0),
            'open': float(candle.get('open', 0)),
            'high': float(candle.get('high', 0)),
            'low': float(candle.get('low', 0)),
            'close': float(candle.get('close', 0)),
            'volume': float(candle.get('volume', 0)),
        })

    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run Flask server."""
        logger.info(f"🌐 Flask server starting on http://0.0.0.0:{port}")
        logger.info(f"🌐 Access at: http://localhost:{port}")
        try:
            self.app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            logger.error(f"Flask error: {e}")

    def run_async(self, port=5000):
        """Run Flask in background thread."""
        thread = threading.Thread(
            target=self.run,
            kwargs={'host': '127.0.0.1', 'port': port, 'debug': False},
            daemon=True
        )
        thread.start()
        logger.info(f"✅ Web server thread started on port {port}")
        return thread
