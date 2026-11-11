"""Server-Side Request Forgery (SSRF) Protection & URL Validation Engine."""

import ipaddress
import socket
from urllib.parse import urlparse

from packages.shared.errors import ChangeScopeBaseError


class SSRFProtectionError(ChangeScopeBaseError):
    """Raised when an outbound URL target violates SSRF network boundaries."""

    status_code = 400
    error_type = "https://changescope.io/errors/ssrf-boundary-violation"
    title = "SSRF Boundary Violation"


# Comprehensive list of blocked IP networks (IPv4 & IPv6)
BLOCKED_IP_NETWORKS = [
    # IPv4 Private, Loopback, Link-Local, and Special
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/GCP/Azure Metadata: 169.254.169.254
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 Loopback, Link-Local, Unique-Local, and Multicast
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
}


class SSRFProtector:
    """Validates outbound HTTP targets to prevent SSRF against internal services or cloud metadata."""

    ALLOWED_SCHEMES = {"http", "https"}

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Determines if an IP address belongs to any restricted private or cloud metadata subnet."""
        try:
            ip = ipaddress.ip_address(ip_str.strip())
        except ValueError:
            return True

        if ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            return True

        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                return True

        return False

    @classmethod
    def validate_url(cls, url: str) -> str:
        """Thoroughly inspects and resolves a target URL, rejecting private/loopback/cloud metadata destinations."""
        if not url or not isinstance(url, str):
            raise SSRFProtectionError("Target URL cannot be empty.")

        parsed = urlparse(url.strip())

        # 1. Enforce Scheme
        if not parsed.scheme or parsed.scheme.lower() not in cls.ALLOWED_SCHEMES:
            raise SSRFProtectionError(f"Prohibited URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

        # 2. Prevent Userinfo / Credential Embeds (e.g., http://user:pass@host)
        if parsed.username or parsed.password:
            raise SSRFProtectionError("Embedded credentials in URL are prohibited.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFProtectionError("Target URL must specify a valid hostname or IP address.")

        hostname_clean = hostname.lower().strip("[]")

        # 3. Block Known Cloud Metadata and Localhost Hostnames
        if hostname_clean in BLOCKED_HOSTNAMES:
            raise SSRFProtectionError(
                f"Target host '{hostname_clean}' is a prohibited loopback or metadata destination."
            )

        # 4. Direct IP address check
        try:
            ip_obj = ipaddress.ip_address(hostname_clean)
            if cls.is_ip_blocked(str(ip_obj)):
                raise SSRFProtectionError(
                    f"Target IP address '{hostname_clean}' is in a prohibited private or metadata network."
                )
            return url
        except ValueError:
            # Hostname is a domain name, proceed to DNS resolution
            pass

        # 5. DNS Resolution and Rebinding Defense
        try:
            addr_info = socket.getaddrinfo(hostname_clean, parsed.port or (443 if parsed.scheme == "https" else 80))
            if not addr_info:
                raise SSRFProtectionError(f"Unable to resolve target host '{hostname_clean}'.")

            for entry in addr_info:
                sockaddr = entry[4]
                resolved_ip = str(sockaddr[0])
                if cls.is_ip_blocked(resolved_ip):
                    raise SSRFProtectionError(
                        f"Target host '{hostname_clean}' resolves to prohibited IP '{resolved_ip}'."
                    )
        except socket.gaierror as exc:
            raise SSRFProtectionError(f"DNS resolution failure for host '{hostname_clean}': {exc}") from exc

        return url
