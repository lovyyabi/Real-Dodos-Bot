from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    welcome_channel_id: Optional[int] = None
    role_log_channel_id: Optional[int] = None
    database_path: str = "data/bot.db"

# Config zum Anpassen der Channel IDs
CONFIG = BotConfig(
    welcome_channel_id=1345156616546422936,
    role_log_channel_id=1480312066811105361,
    database_path="data/bot.db",
)