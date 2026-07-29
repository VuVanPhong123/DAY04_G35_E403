import requests

def crypto_price(*, coin_id: str, currency: str = "usd") -> dict:
    """Fetch current cryptocurrency price from CoinGecko API."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id.lower(),
        "vs_currencies": currency.lower()
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if coin_id.lower() in data:
            price = data[coin_id.lower()][currency.lower()]
            return {
                "coin_id": coin_id,
                "currency": currency,
                "price": price,
                "status": "success"
            }
        else:
            return {
                "error": f"Coin '{coin_id}' not found.",
                "status": "not_found"
            }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error"
        }
