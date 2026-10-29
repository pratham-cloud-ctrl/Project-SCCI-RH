"""Local preview with the same /Project-SCCI-RH/ prefix as the public Pages site."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'inspector'


class Handler(SimpleHTTPRequestHandler):
    def do_HEAD(self):
        if self.path.startswith('/Project-SCCI-RH/'):
            self.path = self.path[len('/Project-SCCI-RH'):]
        super().do_HEAD()

    def do_GET(self):
        if self.path.startswith('/Project-SCCI-RH/'):
            self.path = self.path[len('/Project-SCCI-RH'):]
        elif self.path in ('/', '/Project-SCCI-RH'):
            self.send_response(302)
            self.send_header('Location', '/Project-SCCI-RH/')
            self.end_headers()
            return
        super().do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8801)
    args = parser.parse_args()
    print(f'Project SCCI RH inspector: http://127.0.0.1:{args.port}/Project-SCCI-RH/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT))).serve_forever()
