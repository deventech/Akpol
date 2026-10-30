from app.models.risk_scorer import build_result
from app.models.url_analyzer import analyze_url


def level(url):
    return build_result(analyze_url(url))["level"]


def test_aman():
    assert level("https://google.com") == "lo"


def test_phishing():
    assert level("http://login-update.com/verify") == "hi"
    assert level("http://paypal.secure-login.xyz/account") == "hi"


def test_tidak_valid():
    assert "error" in analyze_url("abc")
    assert "error" in analyze_url("")
