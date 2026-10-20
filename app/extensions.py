import ipaddress
from flask import request
from flask_socketio import SocketIO
from flask_limiter import Limiter


def _ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(text.strip())
    except ValueError:
        return None


def visitor_ip(environ: dict) -> str:
    # In production every request reaches Flask from nginx on 127.0.0.1, so
    # the peer address alone would put the whole internet in one bucket.
    # Cloudflare's tunnel sets CF-Connecting-IP to the real visitor's address.
    # Only trust it from loopback though: anyone talking to Flask directly
    # could put whatever they like in that header.
    peer = environ.get("REMOTE_ADDR") or "unknown"
    peer_ip = _ip(peer)
    if peer_ip and peer_ip.is_loopback:
        cf = _ip(environ.get("HTTP_CF_CONNECTING_IP", ""))
        if cf:
            peer_ip = cf
    if peer_ip is None:
        return peer
    # One IPv6 home gets a whole /64 (billions of addresses), so count the
    # /64 as one visitor or a cap per address means nothing
    if peer_ip.version == 6:
        if peer_ip.ipv4_mapped:
            return str(peer_ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{peer_ip}/64", strict=False))
    return str(peer_ip)


def client_ip() -> str:
    return visitor_ip(request.environ)


socketio = SocketIO()

limiter = Limiter(
    key_func=client_ip,
    default_limits=[],
    storage_uri="memory://",
)
