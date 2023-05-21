"""Dictionary cog for Red-DiscordBot based on Wiktionary."""
import asyncio
import logging

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red


log = logging.getLogger("red.syntheticbee-cogs.RoleTrack")
log.setLevel(logging.DEBUG)


class RoleTrack(commands.Cog):
    """Track changes to selected roles."""

    __author__ = "SyntheticBee"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=39375275624771337830,
        )
        self.config.register_guild(
            tracked_roles=[],
        )
        self._ready: asyncio.Event = asyncio.Event()

    def cog_check(self, ctx: commands.Context) -> bool:
        return self._ready.is_set()

    async def cog_load(self) -> None:
        self._ready.set()

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        await self._ready.wait()
        if await self.bot.cog_disabled_in_guild(self, before.guild):
            return
        tracked_roles = await self.config.guild(before.guild).tracked_roles()
        for role in tracked_roles:
            before_role = before.get_role(role)
            after_role = after.get_role(role)
            if before_role != after_role:
                log.debug("Role %s: %r", "added" if after_role else "removed", role)
                updated_role = before_role or after_role
                log.debug("Members with role %r: %i", role, len(updated_role.members))

    @commands.group()
    @commands.guild_only()
    async def roletrack(self, ctx: commands.Context) -> None:
        """Commands to track number of members with roles."""

    @roletrack.command()
    async def add(self, ctx: commands.Context, role: discord.Role):
        guild_config = self.config.guild(ctx.guild)
        async with guild_config.tracked_roles() as tracked_roles:
            if role.id in tracked_roles:
                await ctx.send(
                    embed=discord.Embed(
                        description=f"Not updated: I am already tracking role: {role.mention}"
                    )
                )
                return
            tracked_roles.append(role.id)
            await ctx.send(
                embed=discord.Embed(
                    description=f"Updated: I will now track role: {role.mention}"
                )
            )

    @roletrack.command()
    async def remove(self, ctx: commands.Context, role: discord.Role):
        guild_config = self.config.guild(ctx.guild)
        async with guild_config.tracked_roles() as tracked_roles:
            if role.id not in tracked_roles:
                await ctx.send(
                    embed=discord.Embed(
                        description=f"Not updated: I am not yet tracking role: {role.mention}"
                    )
                )
                return
            tracked_roles.remove(role.id)
            await ctx.send(
                embed=discord.Embed(
                    description=f"Updated: I will no longer track role: {role.id}"
                )
            )

    @roletrack.command()
    async def list(self, ctx: commands.Context):
        guild_config = self.config.guild(ctx.guild)
        tracked_roles = await guild_config.tracked_roles()
        description = (
            f"Tracked roles: {' '.join(f'<@&{role_id}>' for role_id in tracked_roles)}"
        )
        await ctx.send(embed=discord.Embed(description=description))

    @roletrack.group(name="message")
    async def roletrack_message(self, ctx: commands.Context) -> None:
        """Commands to manage tracked role messages."""

    @roletrack_message.command()
    async def send(
        self, ctx: commands.Context, roles: commands.Greedy[discord.Role]
    ) -> None:
        """Send a role tracker message."""
        log.debug("%r", roles)
        embed = discord.Embed(
            title="Member count per role",
            description="\n".join(
                f"{role.mention}: {len(role.members)}" for role in roles
            ),
        )
        await ctx.send(embed=embed)
