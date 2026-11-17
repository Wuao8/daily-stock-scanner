
import yfinance as yf
import pandas as pd
import json
import time
from datetime import datetime, timezone

print("Daily Stock Scanner avviato")

# Universo iniziale: lo popoleremo automaticamente
# con le borse USA ed europee nel passaggio successivo.
