"""Single Page Application (SPA) HTTP server for Q-FLOW frontend.

Serves pre-built assets from frontend/dist on port 5173.
Routes all non-file requests to index.html for client-side routing.
"""

import http.server
import socketserver
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

PORT = 5173
DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist"))



class SPARequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        # Determine the local file path
        path = self.translate_path(self.path)

        # If path does not exist as a file or directory, serve index.html (SPA fallback)
        # BUT ONLY for non-asset route navigation (do not rewrite /assets/ or filenames with extensions)
        is_asset_or_file = self.path.startswith("/assets/") or bool(os.path.splitext(self.path)[1])
        if not is_asset_or_file and (not os.path.exists(path) or (os.path.isdir(path) and not os.path.exists(os.path.join(path, "index.html")))):
            self.path = "/index.html"

        return super().do_GET()


    def end_headers(self):
        # Enable CORS and disable aggressive caching for local development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")
        super().end_headers()

    def log_message(self, format, *args):
        # Keep terminal output clean: only log requests in debug
        if sys.flags.debug:
            super().log_message(format, *args)


def main():
    if not os.path.exists(DIST_DIR):
        print(f"Error: {DIST_DIR} not found. Please build the frontend first.")
        sys.exit(1)

    # Allow address reuse
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SPARequestHandler) as httpd:
        print(f"[Q-FLOW Frontend] Serving SPA from {DIST_DIR}")
        print(f"[Q-FLOW Frontend] Application live at: http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Q-FLOW Frontend] Server stopped.")


if __name__ == "__main__":
    main()
