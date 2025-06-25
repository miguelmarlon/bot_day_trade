import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN_BOT_TRADE = os.getenv("TELEGRAM_BOT_TOKEN_BOT_TRADE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")