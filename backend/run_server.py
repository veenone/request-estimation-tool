"""Run the FastAPI backend with optional HTTPS support.

Environment variables:
    HOST            Listen address (default: 0.0.0.0)
    PORT            Listen port (default: 8000)
    SSL_CERTFILE    Path to PEM certificate file (enables HTTPS)
    SSL_KEYFILE     Path to PEM private key file (required with SSL_CERTFILE)

Usage:
    python run_server.py                                 # HTTP
    SSL_CERTFILE=certs/cert.pem SSL_KEYFILE=certs/key.pem python run_server.py  # HTTPS
"""

import os

import uvicorn


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    ssl_certfile = os.environ.get("SSL_CERTFILE", "") or None
    ssl_keyfile = os.environ.get("SSL_KEYFILE", "") or None

    kwargs: dict = {
        "app": "src.api.app:app",
        "host": host,
        "port": port,
    }

    if ssl_certfile and ssl_keyfile:
        kwargs["ssl_certfile"] = ssl_certfile
        kwargs["ssl_keyfile"] = ssl_keyfile
        print(f"Starting HTTPS server on https://{host}:{port}")
    else:
        print(f"Starting HTTP server on http://{host}:{port}")

    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()
