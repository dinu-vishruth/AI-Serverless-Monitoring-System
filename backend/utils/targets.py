"""Restrict probes to public HTTP(S) targets; block metadata/private networks."""
import ipaddress
import socket
from urllib.parse import urlsplit
from backend.utils.config import get_settings


def validate_target(url, resolve=False):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Use an HTTP(S) URL without credentials or fragments")
    if get_settings().allow_private_targets and get_settings().environment.lower() in {"local", "dev", "development", "test"}:
        return url
    if parsed.port and parsed.port not in {80, 443}:
        raise ValueError("Public target port must be 80 or 443")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("Private targets are disabled")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = [ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(host, parsed.port or 443)] if resolve else []
    if any(not address.is_global for address in addresses):
        raise ValueError("Private targets are disabled")
    return url


def probe_address(url):
    """Resolve once and pin the validated address for the subsequent connection."""
    validate_target(url)
    parsed = urlsplit(url)
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    private_allowed = get_settings().allow_private_targets and get_settings().environment.lower() in {"local", "dev", "development", "test"}
    if not private_allowed and any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Private targets are disabled")
    if not addresses:
        raise socket.gaierror("No target addresses")
    return addresses[0][4][0]
