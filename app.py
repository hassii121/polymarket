from web_server import WebServer

# Create Flask app for Gunicorn
web_server = WebServer()
app = web_server.app

if __name__ == "__main__":
    web_server.run(host='0.0.0.0', port=5000)
