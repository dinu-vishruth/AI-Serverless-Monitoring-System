import socket
import ssl
import urllib.error
from unittest.mock import Mock, patch
import pytest
from backend.lambdas.health_checker.handler import perform_http_check


@pytest.mark.parametrize("code", [500,503,401,404])
def test_unexpected_status_is_failure(code):
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError("https://example.com", code, "test", {}, None)
    with patch("urllib.request.build_opener", return_value=opener), patch("backend.utils.targets.probe_address", return_value="93.184.216.34"):
        result = perform_http_check("https://example.com")
    assert result["availability"] == 0
    assert result["failure_type"] == "http_status"
    assert result["status_code"] == code


@pytest.mark.parametrize("reason,kind", [(socket.gaierror("DNS"),"dns"),(ssl.SSLError("TLS"),"tls"),(TimeoutError(),"timeout"),(ConnectionRefusedError(),"connection")])
def test_network_failure_types(reason,kind):
    opener = Mock()
    opener.open.side_effect = urllib.error.URLError(reason)
    with patch("urllib.request.build_opener", return_value=opener), patch("backend.utils.targets.probe_address", return_value="93.184.216.34"):
        result = perform_http_check("https://example.com")
    assert result["failure_type"] == kind
    assert result["timeout"] == int(kind == "timeout")
