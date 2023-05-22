"""Cog for Red-DiscordBot to track how many members hold particular roles"""
import asyncio
import logging
from typing import Optional

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red


log = logging.getLogger("red.syntheticbee-cogs.RoleTrack")
log.setLevel(logging.DEBUG)


def get_tracker_message_id_parts(tracker: dict):
    message_id_str = tracker.get("message", "-")
    return (int(part) for part in message_id_str.split("-"))


async def get_tracker_message(
    cog: commands.Cog,
    guild: discord.Guild,
    tracker: dict,
):
    (channel_id, message_id) = get_tracker_message_id_parts(tracker)
    message = next(
        (msg for msg in cog.bot.cached_messages if msg.id == int(message_id)),
        None,
    )
    if not message:
        if message_id not in cog.stale_tracking_messages:
            channel = guild.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
    return message


def make_embed(
    guild: discord.Guild,
    tracked_role_ids: list[int],
    title: Optional[str],
):
    _title = title or "Members per role"
    # Roles or just the id if not found:
    roles_in_embed = [
        guild.get_role(tracked_role_id) or tracked_role_id
        for tracked_role_id in tracked_role_ids
    ]
    description = "\n".join(
        f"Missing role #{role.id}: n/a"
        if isinstance(role, int)
        else f"{role.mention}: {len(role.members)}"
        for role in roles_in_embed
        if role.id in tracked_role_ids
    )
    return discord.Embed(title=_title, description=description)


class RoleTrack(commands.Cog):
    """Track changes to selected roles"""

    __author__ = "SyntheticBee"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=39375275624771337830,
        )
        self.config.register_guild(
            tracked_roles=[],
            tracking_messages=[],
        )
        self._ready: asyncio.Event = asyncio.Event()
        self.stale_tracking_messages: list[int] = []

    def cog_check(self, ctx: commands.Context) -> bool:
        return self._ready.is_set()

    async def cog_load(self) -> None:
        self._ready.set()

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        await self._ready.wait()
        guild = after.guild
        if await self.bot.cog_disabled_in_guild(self, guild):
            return
        changed_roles = set(role for role in after.roles).symmetric_difference(
            role for role in before.roles
        )
        if not changed_roles:
            return
        guild_config = self.config.guild(guild)
        tracked_role_ids = set(await guild_config.tracked_roles())
        if not tracked_role_ids:
            return
        changed_tracked_roles = [
            role for role in changed_roles if role.id in tracked_role_ids
        ]
        if not changed_tracked_roles:
            return
        changed_tracked_role_ids = [role.id for role in changed_tracked_roles]
        # Only update tracker messages with tracked roles that changed for the member:
        trackers = [
            tracker
            for tracker in await guild_config.tracking_messages()
            if set(tracker.get("roles")).intersection(changed_tracked_role_ids)
        ]
        for tracker in trackers:
            try:
                message = await get_tracker_message(self, guild, tracker)
                if not message:
                    continue
                embed = make_embed(
                    guild,
                    tracked_role_ids=tracker.get("roles"),
                    title=tracker.get("title"),
                )
                await message.edit(embed=embed)
            except (
                discord.HTTPException,
                discord.Forbidden,
                ValueError,
                TypeError,
            ) as err:
                # Log & skip messages we can't fetch or edit
                # - also mark them stale to avoid expensive repeat fetches
                (_channel_id, message_id) = get_tracker_message_id_parts(tracker)
                self.stale_tracking_messages.append(message_id)
                log.error(
                    "Stopping %s updates until reload due to: %s",
                    tracker.get("message"),
                    err,
                )
                continue

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permission(manage_roles=True)
    async def roletrack(self, ctx: commands.Context) -> None:
        """Commands to track number of members with roles"""

    @roletrack.group(name="role")
    async def roletrack_role(self, ctx: commands.Context) -> None:
        """Commands to manage tracked roles"""

    @roletrack_role.command(name="add")
    async def roletrack_role_add(self, ctx: commands.Context, role: discord.Role):
        """Add a role to track"""
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

    @roletrack_role.command(name="remove")
    async def roletrack_role_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove a tracked role"""
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

    @roletrack_role.command(name="list")
    async def roletrack_role_list(self, ctx: commands.Context):
        """List tracked roles"""
        guild_config = self.config.guild(ctx.guild)
        tracked_roles = await guild_config.tracked_roles()
        description = (
            f"Tracked roles: {' '.join(f'<@&{role_id}>' for role_id in tracked_roles)}"
        )
        await ctx.send(embed=discord.Embed(description=description))

    @roletrack.group(name="message")
    async def roletrack_message(self, ctx: commands.Context) -> None:
        """Commands to manage tracked role messages"""

    @roletrack_message.command(name="send")
    async def roletrack_message_send(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        roles: commands.Greedy[discord.Role] = [],
        title: Optional[str] = None,
    ) -> None:
        """Send a role tracker message and start tracking"""
        _channel = channel or ctx.channel
        guild_config = self.config.guild(ctx.guild)
        tracked_role_ids = set(await guild_config.tracked_roles())
        message_role_ids = set(role.id for role in roles)
        untracked_roles = [
            ctx.guild.get_role(role_id)
            for role_id in (message_role_ids - tracked_role_ids)
        ]
        if untracked_roles:
            msg = " ".join(role.mention for role in untracked_roles)
            embed = discord.Embed(
                description=(
                    f"Role tracker not created as these roles are untracked: {msg}.\n"
                    "- List currently tracked roles with: `[p]roletrack list`\n"
                    "- Add each new tracked role with: `[p]roletrack add <role>`"
                ),
            )
            await ctx.send(embed=embed)
            return

        error_msg = None
        try:
            embed = make_embed(
                ctx.guild,
                tracked_role_ids,
                title=title,
            )
            message = await _channel.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            message = None
        if message:
            async with self.config.guild(
                ctx.guild
            ).tracking_messages() as tracking_messages:
                tracking_messages.append(
                    {
                        "message": f"{_channel.id}-{message.id}",
                        "title": title,
                        "roles": [role.id for role in roles],
                    }
                )
            await ctx.send(
                "Role tracking message sent; changes to members per role will be updated."
            )
        else:
            await ctx.send(f"Role tracking message not created:\n{error_msg}")

    @roletrack_message.command(name="purge")
    async def roletrack_message_purge(
        self,
        ctx: commands.Context,
    ) -> None:
        """Purge inaccessible role tracker messages from config"""
        guild_config = self.config.guild(ctx.guild)
        valid = []
        invalid = []
        for tracker in await guild_config.tracking_messages():
            try:
                message = await get_tracker_message(self, ctx.guild, tracker)
                if message:
                    valid.append(tracker)
                else:
                    raise ValueError(
                        "Tracker message not in cache and not fetched into cache"
                    )
            except (discord.HTTPException, discord.Forbidden, ValueError):
                invalid.append(tracker)
        if not valid and not invalid:
            await ctx.send("No role trackers defined")
            return
        if invalid:
            await ctx.send(
                "Purging these no longer accessible role trackers from config:\n"
                + "\n".join(repr(tracker) for tracker in invalid)
            )
            async with guild_config.tracking_messages() as tracking_messages:
                for invalid_tracker in invalid:
                    tracking_messages.remove(invalid_tracker)
        if valid:
            await ctx.send(
                "Valid role trackers remaining:\n"
                + "\n".join(repr(tracker) for tracker in valid)
            )

    @roletrack_message.command(name="list")
    async def roletrack_message_list(
        self,
        ctx: commands.Context,
    ) -> None:
        """List role tracking message config stanzas"""
        guild_config = self.config.guild(ctx.guild)
        valid = []
        invalid = []
        for tracker in await guild_config.tracking_messages():
            try:
                message = await get_tracker_message(self, ctx.guild, tracker)
                if message:
                    valid.append(tracker)
                else:
                    raise ValueError(
                        "Tracker message not in cache and not fetched into cache"
                    )
            except (discord.HTTPException, discord.Forbidden, ValueError):
                invalid.append(tracker)
        if not valid and not invalid:
            await ctx.send("No role trackers defined")
            return
        if invalid:
            await ctx.send(
                "Inaccessible role trackers:\n"
                + "\n".join(repr(tracker) for tracker in invalid)
                + "\n\nTo remove them from config, use: `[p]roletrack message purge`"
            )
        if valid:
            await ctx.send(
                "Valid role trackers:\n" + "\n".join(repr(tracker) for tracker in valid)
            )
