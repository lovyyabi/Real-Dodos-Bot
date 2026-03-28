import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

class DodosBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.load_extension("commands.commands")
        await self.tree.sync()
        print("Slash-Commands synchronisiert!")

    async def on_ready(self) -> None:
        print(f"Bot eingeloggt als {self.user} (ID: {self.user.id})")
        print("------")

async def main() -> None:
    bot = DodosBot()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN nicht in .env gefunden!")
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())