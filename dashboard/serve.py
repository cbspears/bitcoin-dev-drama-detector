#!/usr/bin/env python3
"""
Simple HTTP server for Bitcoin Dev Drama Detector dashboard.
Run from the project root directory.
"""

import http.server
import socketserver
import os
from pathlib import Path

# Change to project root
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

PORT = 8000

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()

if __name__ == '__main__':
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║  Bitcoin Dev Drama Detector Dashboard       ║
    ╚══════════════════════════════════════════════╝

    🚀 Server starting on port {PORT}...

    📊 Open dashboard at:
       http://localhost:{PORT}/dashboard/

    💡 Data files location:
       {PROJECT_ROOT}/data/processed/

    Press Ctrl+C to stop the server
    """)

    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped. Thanks for using Drama Detector!")
