import logging
from typing import Optional
import discord
from discord.ext import commands
from discord.ui import Container, Section, TextDisplay, Thumbnail, LayoutView

class EventListeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    def _get_text_channel(self, channel_id: Optional[int]) -> Optional[discord.TextChannel]:
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @staticmethod
    def _build_layout_view(container: Container) -> LayoutView:
        view = LayoutView()
        view.add_item(container)
        return view

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        is_new = self.db.record_member_join(
            guild_id=member.guild.id,
            user_id=member.id,
            joined_at=member.joined_at,
        )

        channel_id = getattr(self.bot.config, "welcome_channel_id", None)
        channel = self._get_text_channel(channel_id)
        if channel is None:
            logging.debug("Willkommenskanal nicht gesetzt oder nicht gefunden; überspringe Nachricht.")
            return

        description = f"Hey {member.mention}, willkommen auf **{member.guild.name}**!"
        if is_new:
            description += "\nDies ist dein erster Besuch hier!"
        else:
            description += "\nSchön, dass du wieder da bist!"

        created_rel = f"Account erstellt: <t:{int(member.created_at.timestamp())}:R>"

        container = Container(
            Section(
                TextDisplay("🎉 **Neues Mitglied**"),
                TextDisplay(description),
                TextDisplay(created_rel),
                accessory=Thumbnail(media=member.display_avatar.url),
            ),
            TextDisplay(f"User-ID: `{member.id}`"),
            accent_colour=discord.Color.blurple().value,
        )
        view = self._build_layout_view(container)

        try:
            await channel.send(view=view)
        except Exception:
            logging.exception("Fehler beim Versenden der Willkommensnachricht")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        self.db.record_member_leave(member.guild.id, member.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        channel_id = getattr(self.bot.config, "role_log_channel_id", None)
        channel = self._get_text_channel(channel_id)
        if channel is None:
            return

        before_roles = {role.id for role in before.roles if role.name != "@everyone"}
        after_roles = {role.id for role in after.roles if role.name != "@everyone"}

        added_ids = after_roles - before_roles
        removed_ids = before_roles - after_roles

        if not added_ids and not removed_ids:
            return

        added_roles = [role.mention for role in after.roles if role.id in added_ids]
        removed_roles = [role.mention for role in before.roles if role.id in removed_ids]

        description_lines = []
        if added_roles:
            description_lines.append(f"Hinzugefügt: {', '.join(added_roles)}")
        if removed_roles:
            description_lines.append(f"Entfernt: {', '.join(removed_roles)}")

        description = "\n".join(description_lines)

        container = Container(
            Section(
                TextDisplay("🛡️ **Rollenaktualisierung**"),
                TextDisplay(description or "Keine Änderungen"),
                TextDisplay(f"User: {after.mention}"),
                accessory=Thumbnail(media=after.display_avatar.url),
            ),
            TextDisplay(f"User-ID: `{after.id}`"),
            accent_colour=discord.Color.gold().value,
        )
        view = self._build_layout_view(container)

        try:
            await channel.send(view=view)
        except Exception:
            logging.exception("Fehler beim Versenden des Rollen-Logs")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventListeners(bot))