import logging
from web_server import WebServer
from bot import PolymarketBot

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create bot instance (for APIs)
bot = PolymarketBot()

# Create Flask app
app = bot.web_server.app

if __name__ == "__main__":
    bot.web_server.run(host='0.0.0.0', port=5000)
