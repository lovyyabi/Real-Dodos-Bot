import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import BotConfig, CONFIG
from database import DatabaseManager

load_dotenv()

class DodosBot(commands.Bot):
    def __init__(self, config: BotConfig, db_manager: DatabaseManager) -> None:
        self.config = config
        self.db = db_manager

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.load_extension("commands.commands")
        await self.load_extension("events.listeners")
        await self.tree.sync()
        print("Slash-Commands synchronisiert!")

    async def on_ready(self) -> None:
        for guild in self.guilds:
            members_payload = [
                (member.id, member.joined_at)
                for member in guild.members
            ]
            self.db.sync_guild_members(guild.id, members_payload)
        print(f"Bot eingeloggt als {self.user} (ID: {self.user.id})")
        print("------")

    async def close(self) -> None:
        await super().close()
        self.db.close()

async def main() -> None:
    db_manager = DatabaseManager(CONFIG.database_path)
    bot = DodosBot(CONFIG, db_manager)

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN nicht in .env gefunden!")
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())