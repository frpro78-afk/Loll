from pathlib import Path

FORBIDDEN_TOKENS = [
    "/api/v3/order",   # real order placement endpoint
    "x-mbx-apikey",    # exchange API-key header
    "api_secret",
    "/sapi/",          # signed exchange endpoints
    "fapi",            # futures API
]


def test_app_contains_no_real_trading_or_futures_code():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert offenders == []
