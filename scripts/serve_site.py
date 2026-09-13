"""Build and serve the playground locally. Ctrl+C stops the server."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build_site import ROOT, build


if __name__ == "__main__":
    build()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "dist")))
    print("Tenioha playground: http://127.0.0.1:8765", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
