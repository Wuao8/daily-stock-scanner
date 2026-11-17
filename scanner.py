import json
import time
from datetime import datetime, timezone

import yfinance as yf
import pandas as pd

# CONFIGURAZIONE
MIN_EUR = 19.0
MAX_EUR = 39.0
BATCH_SIZE = 40
PAUSE = 3

# Regioni USA ed Europa supportate da Yahoo Finance
REGIONS = [
    "us", "gb", "de", "fr", "it", "ch", "nl",
    "be", "es", "pt", "at", "ie", "dk", "se",
    "no", "fi", "pl", "gr", "cz", "hu", "ro",
    "is", "ee", "lt", "lv"
]

def get_universe():
    stocks = {}
    failed_regions = []

    print("Ricerca automatica delle azioni...")

    for region in REGIONS:
        offset = 0

        try:
            while True:
                query = yf.EquityQuery(
                    "eq", ["region", region]
                )

                result = yf.screen(
                    query,
                    offset=offset,
                    size=250
                )

                quotes = result.get("quotes", [])

                for q in quotes:
                    symbol = q.get("symbol")
                    currency = q.get("currency")

                    if symbol and currency:
                        stocks[symbol] = {
                            "name": q.get("longName")
                                     or q.get("shortName")
                                     or symbol,
                            "currency": currency,
                            "region": region
                        }

                if len(quotes) < 250:
                    break

                offset += 250
                time.sleep(PAUSE)

        except Exception as e:
            print(f"Errore regione {region}: {e}")
            failed_regions.append(region)

        print(region, ":", len(stocks), "titoli raccolti")
        time.sleep(PAUSE)

    return stocks, failed_regions



def get_eur_rate(currency):
    if currency == "EUR":
        return 1.0

    divisor = 100 if currency in ("GBp", "GBX") else 1
    base_currency = "GBP" if divisor == 100 else currency

    try:
        pair = f"{base_currency}EUR=X"
        data = yf.Ticker(pair).history(period="5d")

        if data.empty:
            return None

        rate = float(data["Close"].dropna().iloc[-1])
        return rate / divisor

    except Exception:
        return None



def check_signals(df):
    if df is None or len(df) < 60:
        return None

    close = df["Close"].dropna()

    if len(close) < 60:
        return None

    ema20 = close.ewm(
        span=20,
        adjust=False
    ).mean()

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26
    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    # Ultima candela contro la precedente
    ema_cross = (
        close.iloc[-2] <= ema20.iloc[-2]
        and close.iloc[-1] > ema20.iloc[-1]
    )

    macd_cross = (
        macd.iloc[-2] <= signal.iloc[-2]
        and macd.iloc[-1] > signal.iloc[-1]
    )

    if ema_cross and macd_cross:
        return float(close.iloc[-1])

    return None


def main():
    stocks, failed_regions = get_universe()

    print("Totale titoli:", len(stocks))

    results = []
    errors = 0
    checked = 0

    symbols = list(stocks.keys())

    for start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[start:start + BATCH_SIZE]

        try:
            data = yf.download(
                batch,
                period="4mo",
                interval="1d",
                auto_adjust=True,
                group_by="ticker",
                threads=False,
                progress=False
            )

            for symbol in batch:
                try:
                    if len(batch) == 1:
                        df = data
                    else:
                        df = data[symbol]

                    if df.empty:
                        errors += 1
                        continue

                    price = check_signals(df)

                    if price is None:
                        checked += 1
                        continue

                    currency = stocks[symbol]["currency"]
                    rate = get_eur_rate(currency)

                    if rate is None:
                        errors += 1
                        continue

                    price_eur = price * rate

                    if MIN_EUR <= price_eur <= MAX_EUR:
                        results.append({
                            "symbol": symbol,
                            "name": stocks[symbol]["name"],
                            "currency": currency,
                            "price": round(price, 4),
                            "price_eur": round(price_eur, 2),
                            "date": str(df.index[-1].date()),
                            "ema20": True,
                            "macd": True
                        })

                    checked += 1

                except Exception as e:
                    errors += 1
                    print("Errore titolo:", symbol, e)

        except Exception as e:
            errors += len(batch)
            print("Errore batch:", e)

        print(
            f"Analizzati: {min(start + len(batch), len(symbols))}"
            f"/{len(symbols)} | Segnali: {len(results)}"
        )

        time.sleep(PAUSE)

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_found": len(stocks),
        "checked": checked,
        "errors": errors,
        "failed_regions": failed_regions,
        "complete": not failed_regions and errors == 0,
        "results": results
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("SCANNER TERMINATO")
    print("Segnali trovati:", len(results))
    print("Errori:", errors)


if __name__ == "__main__":
    main()
