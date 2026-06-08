from web_server import WebServer

# Create just the Flask app (no bot async stuff)
ws = WebServer(bot=None)
app = ws.app
