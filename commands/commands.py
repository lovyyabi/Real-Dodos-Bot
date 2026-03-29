import logging
from datetime import datetime
import psutil
import discord
from typing import List, Optional, Tuple
from discord import app_commands
from discord.ext import commands
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

    @app_commands.command(name="ping", description="Zeigt die Latenz und CPU-Auslastung")
    async def ping(self, interaction: discord.Interaction) -> None:
        command_history.record(interaction.user.id, "/ping")
        self.db.log_command(interaction.user.id, "/ping", interaction.guild_id)

        try:
            latency_ms = round(self.bot.latency * 1000)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            embed = discord.Embed(
                title="Pong!",
                color=discord.Color.green()
            )
            embed.add_field(name="Bot Latenz", value=f"{latency_ms}ms", inline=True)
            embed.add_field(name="Server CPU", value=f"{cpu_percent}%", inline=True)

            await interaction.response.send_message(embed=embed)
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

            embed = discord.Embed(
                title=f"Userinfo für {embed_subject.display_name}",
                color=(
                    embed_subject.color
                    if isinstance(embed_subject, discord.Member) and embed_subject.color != discord.Color.default()
                    else discord.Color.blue()
                ),
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)

            embed.add_field(name="Username", value=f"`{target_user.name}`", inline=True)
            embed.add_field(name="Anzeigename", value=f"`{embed_subject.display_name}`", inline=True)
            embed.add_field(name="User-ID", value=f"`{target_user.id}`", inline=True)

            created_at_unix = int(target_user.created_at.timestamp())
            joined_at_unix = (
                int(target_member.joined_at.timestamp())
                if target_member and target_member.joined_at
                else None
            )

            embed.add_field(name="Account erstellt", value=f"<t:{created_at_unix}:F>", inline=True)
            if joined_at_unix:
                embed.add_field(name="Server beigetreten", value=f"<t:{joined_at_unix}:F>", inline=True)
            else:
                embed.add_field(name="Server beigetreten", value="Unbekannt", inline=True)
            embed.add_field(name="Bot", value="Ja" if target_user.bot else "Nein", inline=True)

            nickname_value = (
                f"`{target_member.nick}`" if target_member and target_member.nick else "Keiner"
            )
            embed.add_field(name="Nickname", value=nickname_value, inline=True)

            highest_role = (
                target_member.top_role.mention
                if target_member and target_member.top_role and target_member.top_role.name != "@everyone"
                else "Keine"
            )
            embed.add_field(name="Höchste Rolle", value=highest_role, inline=True)

            roles = []
            if target_member:
                roles = [role.mention for role in target_member.roles if role.name != "@everyone"]

            roles_text = ", ".join(roles) if roles else "Keine"
            if len(roles_text) > 1024:
                roles_text = roles_text[:1021] + "..."
            embed.add_field(name=f"Rollen ({len(roles)})", value=roles_text, inline=False)

            embed.add_field(name="Letzte 5 Befehle", value=f"```{commands_text}```", inline=False)

            embed.set_footer(text=f"Angefragt von {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            await interaction.response.send_message(
                embed=embed,
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

        embed = discord.Embed(
            title=f"Server-Statistiken – {guild.name}",
            color=discord.Color.teal(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Mitglieder online", value=str(online_members), inline=True)
        embed.add_field(name="Mitglieder gesamt", value=str(total_members), inline=True)
        embed.add_field(name="Neue Mitglieder (30 Tage)", value=str(new_members_30), inline=True)
        embed.add_field(name="Befehle gesamt", value=str(total_commands), inline=True)
        embed.set_footer(
            text=f"Angefragt von {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandsCog(bot))