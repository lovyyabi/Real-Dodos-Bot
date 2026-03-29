import logging
from datetime import datetime
import psutil
import discord
from typing import List, Optional, Tuple
from discord import app_commands
from discord.ext import commands
from discord.ui import Container, Section, TextDisplay, Thumbnail, LayoutView

from utils.command_history import command_history


class CommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @staticmethod
    def _format_history(entries: List[Tuple[str, str]]) -> str:
        lines = []
        for idx, (command_name, timestamp) in enumerate(entries, start=1):
            unix_ts = None
            try:
                unix_ts = int(datetime.fromisoformat(timestamp).timestamp())
            except ValueError:
                pass
            time_part = f" – <t:{unix_ts}:R>" if unix_ts else ""
            lines.append(f"{idx}. {command_name}{time_part}")
        return "\n".join(lines)

    @staticmethod
    def _build_layout_view(container: Container) -> LayoutView:
        view = LayoutView()
        view.add_item(container)
        return view

    @app_commands.command(name="ping", description="Zeigt die Latenz und CPU-Auslastung")
    async def ping(self, interaction: discord.Interaction) -> None:
        command_history.record(interaction.user.id, "/ping")
        self.db.log_command(interaction.user.id, "/ping", interaction.guild_id)

        try:
            latency_ms = round(self.bot.latency * 1000)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            bot_avatar = (
                self.bot.user.display_avatar.url
                if self.bot.user
                else "https://cdn.discordapp.com/embed/avatars/0.png"
            )

            container = Container(
                Section(
                    TextDisplay("🏓 **Ping & Systemstatistiken**"),
                    TextDisplay(f"Bot Latenz: `{latency_ms}ms`"),
                    TextDisplay(f"Server CPU: `{cpu_percent}%`"),
                    accessory=Thumbnail(media=bot_avatar),
                ),
                accent_colour=discord.Color.green().value,
            )
            view = self._build_layout_view(container)

            await interaction.response.send_message(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as exc:
            logging.exception("Fehler bei /ping")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Beim Ausführen von /ping ist ein Fehler aufgetreten.",
                    ephemeral=True
                )

    @app_commands.command(name="userinfo", description="Zeigt Informationen über einen User")
    @app_commands.describe(user="Optional: Ein anderer User (nur für Admins)")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
    ) -> None:
        command_history.record(interaction.user.id, "/userinfo")
        self.db.log_command(interaction.user.id, "/userinfo", interaction.guild_id)

        if interaction.guild is None:
            await interaction.response.send_message(
                "Dieser Command kann nur auf einem Server verwendet werden.",
                ephemeral=True
            )
            return

        try:
            guild = interaction.guild

            requesting_member = guild.get_member(interaction.user.id)
            target_user = user or interaction.user

            if user is not None:
                if requesting_member is None or not requesting_member.guild_permissions.administrator:
                    await interaction.response.send_message(
                        "Du benötigst Administrator-Rechte, um andere User abzufragen!",
                        ephemeral=True
                    )
                    return

            target_member = guild.get_member(target_user.id)
            if user is not None and target_member is None:
                await interaction.response.send_message(
                    "Der angegebene User ist nicht auf diesem Server.",
                    ephemeral=True
                )
                return

            embed_subject = target_member or target_user

            history_entries = self.db.get_last_commands_for_user(
                target_user.id,
                limit=5,
                guild_id=guild.id,
            )
            commands_text = (
                self._format_history(history_entries)
                if history_entries
                else "Keine Befehle bisher"
            )

            avatar_url = target_user.display_avatar.url
            accent_colour = (
                embed_subject.color.value
                if isinstance(embed_subject, discord.Member) and embed_subject.color != discord.Color.default()
                else discord.Color.blue().value
            )

            created_at_unix = int(target_user.created_at.timestamp())
            joined_at_unix = (
                int(target_member.joined_at.timestamp())
                if target_member and target_member.joined_at
                else None
            )

            nickname_value = (
                f"`{target_member.nick}`" if target_member and target_member.nick else "Keiner"
            )

            highest_role = (
                target_member.top_role.mention
                if target_member and target_member.top_role and target_member.top_role.name != "@everyone"
                else "Keine"
            )

            roles = []
            if target_member:
                roles = [role.mention for role in target_member.roles if role.name != "@everyone"]

            roles_text = ", ".join(roles) if roles else "Keine"
            if len(roles_text) > 1024:
                roles_text = roles_text[:1021] + "..."

            container = Container(
                Section(
                    TextDisplay(f"**Userinfo für {embed_subject.display_name}**"),
                    TextDisplay(f"Username: `{target_user.name}`"),
                    TextDisplay(f"User-ID: `{target_user.id}`"),
                    accessory=Thumbnail(media=avatar_url),
                ),
                TextDisplay(
                    f"Account erstellt: <t:{created_at_unix}:F>\n"
                    f"Server beigetreten: {f'<t:{joined_at_unix}:F>' if joined_at_unix else 'Unbekannt'}\n"
                    f"Bot: {'Ja' if target_user.bot else 'Nein'}"
                ),
                TextDisplay(
                    f"Nickname: {nickname_value} | Höchste Rolle: {highest_role}"
                ),
                TextDisplay(f"Rollen ({len(roles)}): {roles_text}"),
                TextDisplay(f"Letzte 5 Befehle:\n```{commands_text}```"),
                accent_colour=accent_colour,
            )
            view = self._build_layout_view(container)

            await interaction.response.send_message(
                view=view,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except Exception as exc:
            logging.exception("Fehler bei /userinfo")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Beim Abrufen der Userinfo ist ein Fehler aufgetreten.",
                    ephemeral=True
                )

    @app_commands.command(name="stats", description="Zeigt Server-Statistiken")
    async def stats(self, interaction: discord.Interaction) -> None:
        command_history.record(interaction.user.id, "/stats")
        self.db.log_command(interaction.user.id, "/stats", interaction.guild_id)

        if interaction.guild is None:
            await interaction.response.send_message(
                "Dieser Command funktioniert nur auf Servern.",
                ephemeral=True
            )
            return

        guild = interaction.guild

        total_members = self.db.get_total_members_all_time(guild.id)
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
        new_members_30 = self.db.get_new_member_count(guild.id, days=30)
        total_commands = self.db.get_total_commands(guild.id)

        guild_icon = guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        now_unix = int(discord.utils.utcnow().timestamp())

        container = Container(
            Section(
                TextDisplay(f"**Server-Statistiken – {guild.name}**"),
                TextDisplay(f"Mitglieder online: **{online_members}**"),
                TextDisplay(f"Mitglieder gesamt: **{total_members}**"),
                accessory=Thumbnail(media=guild_icon),
            ),
            TextDisplay(f"Neue Mitglieder (30 Tage): **{new_members_30}**"),
            TextDisplay(f"Befehle gesamt: **{total_commands}**"),
            TextDisplay(
                f"Aktualisiert: <t:{now_unix}:t> – Angefragt von {interaction.user.display_name}"
            ),
            accent_colour=discord.Color.teal().value,
        )
        view = self._build_layout_view(container)

        await interaction.response.send_message(
            view=view,
            allowed_mentions=discord.AllowedMentions.none()
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandsCog(bot))