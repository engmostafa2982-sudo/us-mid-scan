"""Collect the full US $5-$20 universe via the EODHD screener.
Buckets the price range into slices to stay under the screener offset cap."""
import os, json, time, requests, csv

HERE = os.path.dirname(os.path.abspath(__file__))

def load_key():
    key = os.environ.get("EODHD_API_KEY", "")
    if key:
        return key
    env_path = os.path.join(HERE, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("EODHD_API_KEY"):
                    return line.strip().split("=", 1)[1]
    raise RuntimeError("EODHD_API_KEY not found in env or .env file")

KEY = load_key()
BASE_URL = "https://eodhd.com/api/screener"

# Price buckets: $5.00-$10.00 in 0.50 slices, $10.00-$20.00 in 1.00 slices
low  = [round(5.0  + 0.50 * i, 2) for i in range(0, 10)]   # 5.00 .. 9.50
high = [round(10.0 + 1.00 * i, 2) for i in range(0, 10)]   # 10.00 .. 19.00
edges = low + high + [20.0001]
buckets = list(zip(edges[:-1], edges[1:]))

def collect_universe(out_path=None):
    if out_path is None:
        out_path = os.path.join(HERE, "universe.csv")

    seen = {}
    calls = 0

    print("Fetching US $5-$20 universe from EODHD screener...")
    for lo, hi in buckets:
        offset = 0
        while True:
            filters = [["exchange", "=", "us"],
                       ["adjusted_close", ">=", lo],
                       ["adjusted_close", "<",  hi]]
            params = {
                "api_token": KEY,
                "filters": json.dumps(filters),
                "sort": "market_capitalization.desc",
                "limit": 100,
                "offset": offset,
            }
            try:
                r = requests.get(BASE_URL, params=params, timeout=60)
                calls += 1
                if r.status_code != 200:
                    print(f"  ! {lo:.2f}-{hi:.2f} offset {offset} -> HTTP {r.status_code}")
                    break
                rows = r.json().get("data", [])
                if not rows:
                    break
                for x in rows:
                    code = x.get("code")
                    if code and code not in seen:
                        seen[code] = x
                print(f"  bucket {lo:.2f}-{hi:.2f} offset {offset}: +{len(rows)} (total {len(seen)})")
                if len(rows) < 100:
                    break
                offset += 100
                if offset >= 1000:
                    print(f"  ! bucket {lo:.2f}-{hi:.2f} hit offset cap")
                    break
                time.sleep(0.2)
            except Exception as e:
                print(f"  Error at {lo:.2f}-{hi:.2f} offset {offset}: {e}")
                break

    print(f"\nDONE: {len(seen)} unique tickers, {calls} screener calls")

    cols = ["code", "name", "adjusted_close", "market_capitalization", "avgvol_200d",
            "avgvol_1d", "earnings_share", "dividend_yield", "sector", "industry",
            "exchange", "currency_symbol"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for x in seen.values():
            w.writerow(x)

    print(f"Saved -> {out_path}")
    return list(seen.values())

if __name__ == "__main__":
    collect_universe()
