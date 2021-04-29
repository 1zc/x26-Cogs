"""
Simplebansync - A simple, no frills bansync cog
Copyright (C) 2020  Twentysix (https://github.com/Twentysix26/)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import GuildConverter
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import inline
from enum import Enum
from collections import Counter
import discord
import logging
import asyncio

# red 3.0 backwards compatibility support
listener = getattr(commands.Cog, "listener", None)

if listener is None:  # thanks Sinbad
    def listener(name=None):
        return lambda x: x
log = logging.getLogger("red.x26cogs.simplebansync")

class Operation(Enum):
    Pull = 1
    Push = 2
    Sync = 3

class Sbansync(commands.Cog):
    """Pull, push and sync bans between servers"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=262626, force_registration=True
        )
        self.config.register_guild(allow_pull_from=[], allow_push_to=[])

    @commands.group()
    @commands.guild_only()
    @commands.admin()
    async def sbansync(self, ctx: commands.Context):
        """Pull, push and sync bans between servers"""
        if await self.callout_if_fake_admin(ctx):
            ctx.invoked_subcommand = None

    @sbansync.command(name="pull")
    @commands.bot_has_permissions(ban_members=True)
    async def sbansyncpullfrom(self, ctx: commands.Context, *, server: GuildConverter):
        """Pulls bans from a server

        The command issuer must be an admin on that server OR the server
        needs to whitelist this one for pull operations"""
        author = ctx.author
        if not await self.is_member_allowed(Operation.Pull, author, server):
            return await ctx.send("This server is not in that server's pull list.")

        async with ctx.typing():
            try:
                stats = await self.do_operation(Operation.Pull, author, server, f"Manual Ban Sync issued by {author} ({author.id})")
            except RuntimeError as e:
                return await ctx.send(str(e))

        text = ""

        if stats:
            for k, v in stats.items():
                text += f"{k} {v}\n"
        else:
            text = "No bans to pull."

        await ctx.send(text)

    @sbansync.command(name="push")
    @commands.bot_has_permissions(ban_members=True)
    async def sbansyncpushto(self, ctx: commands.Context, *, server: GuildConverter):
        """Pushes bans to a server

        The command issuer must be an admin on that server OR the server
        needs to whitelist this one for push operations"""
        author = ctx.author
        if not await self.is_member_allowed(Operation.Push, author, server):
            return await ctx.send("This server is not in that server's push list.")

        async with ctx.typing():
            try:
                stats = await self.do_operation(Operation.Push, author, server, f"Manual Ban Sync issued by {author} ({author.id})")
            except RuntimeError as e:
                return await ctx.send(str(e))

        text = ""

        if stats:
            for k, v in stats.items():
                text += f"{k} {v}\n"
        else:
            text = "No bans to push."

        await ctx.send(text)

    @sbansync.command(name="sync")
    @commands.bot_has_permissions(ban_members=True)
    async def sbansyncsyncwith(self, ctx: commands.Context, *, server: GuildConverter):
        """Syncs bans with a server

        The command issuer must be an admin on that server OR the server
        needs to whitelist this one for push and pull operations"""
        author = ctx.author
        if not await self.is_member_allowed(Operation.Sync, author, server):
            return await ctx.send("This server is not in that server's push and/or pull list.")

        async with ctx.typing():
            try:
                stats = await self.do_operation(Operation.Sync, author, server, f"Manual Ban Sync issued by {author} ({author.id})")
            except RuntimeError as e:
                return await ctx.send(str(e))

        text = ""

        if stats:
            for k, v in stats.items():
                text += f"{k} {v}\n"
        else:
            text = "No bans to sync."

        await ctx.send(text)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        Ban = await guild.fetch_ban(user)
        Reason = f"{Ban.reason} <{guild.name}>"
        b = self.bot
        logChannel = b.get_channel(827821096828272660)

        push = await self.config.guild(guild).allow_push_to()
        for server in push:
            await asyncio.sleep(3) # cool down
            try:
                if not b.get_guild(server).me.guild_permissions.ban_members:
                    await logChannel.send(f"[BAN SYNC]: :stop_sign: **FATAL**: A ban on <@{user.id}> (`{user.id}`) has __FAILED__ to push from `{guild.name}` to `{b.get_guild(server).name}`. \n> Fatal Error: `NOT AUTHORIZED IN TARGET SERVER. PLEASE REVIEW BOT AUTHORIZATION IMMEDIATELY.`")
                else:
                    server_bans = [await b.get_guild(server).bans()]
                    if user not in server_bans:
                        await b.get_guild(server).ban(user, delete_message_days=0, reason=Reason)
                        await logChannel.send(f"[BAN SYNC]: :white_check_mark: A ban on <@{user.id}> (`{user.id}`) has been pushed from `{guild.name}` to `{b.get_guild(server).name}`. \n> Details: `{Ban.reason}`")

            except discord.HTTPException as E:
                await logChannel.send(f"[BAN SYNC]: :warning: **ALERT**: A ban on <@{user.id}> (`{user.id}`) has __FAILED__ to push from `{guild.name}` to `{b.get_guild(server).name}`. \n> Exception: `{E.status}`")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        b = self.bot
        logChannel = b.get_channel(827821096828272660)

        push = await self.config.guild(guild).allow_push_to()

        for server in push:
            await asyncio.sleep(3) # cool down
            try:
                if not b.get_guild(server).me.guild_permissions.ban_members:
                    await logChannel.send(f"[BAN SYNC]: :stop_sign: **FATAL**: An unban on <@{user.id}> (`{user.id}`) has __FAILED__ to push from `{guild.name}` to `{b.get_guild(server).name}`. \n> Fatal Error: `NOT AUTHORIZED IN TARGET SERVER. PLEASE REVIEW BOT AUTHORIZATION IMMEDIATELY.`")
                else:
                    await b.get_guild(server).unban(user, reason=f"Globally unbanned from <{guild.name}>")
                    await logChannel.send(f"[BAN SYNC]: :white_check_mark: An unban on <@{user.id}> (`{user.id}`) has been pushed from `{guild.name}` to `{b.get_guild(server).name}`.")
            
            except discord.HTTPException as E:
                await logChannel.send(f"[BAN SYNC]: :warning: **ALERT**: An unban on <@{user.id}> (`{user.id}`) has __FAILED__ to push from `{guild.name}` to `{b.get_guild(server).name}`. \n> Exception: `{E.status}`")

    @sbansync.command(name="pushall")
    @commands.bot_has_permissions(ban_members=True)
    async def sbansyncpushall(self, ctx: commands.Context):
        """Push bans to all servers in push list
        
        The command issuer must be an admin on that server OR the server
        needs to whitelist this one for push operations"""
        author = ctx.author
        b = self.bot

        push = await self.config.guild(ctx.guild).allow_push_to()

        async with ctx.typing():
            await ctx.send(f":warning: Commencing global ban push.")
            for server in push:
                await ctx.send(f":outbox_tray: Pushing new bans to server: {b.get_guild(server).name} ({server})")
                try:
                    stats = await self.do_operation(Operation.Push, author, b.get_guild(server), f"Manual Ban Sync issued by {author} ({author.id})")
                except RuntimeError as e:
                    return await ctx.send(str(e))
                    
                text = ""

                if stats:
                    for k, v in stats.items():
                        text += f"{k} {v}\n"
                else:
                    text = f":ballot_box_with_check: No new bans to push to {b.get_guild(server).name} ({server})."
                    
                await ctx.send(text)

        await ctx.send(":white_check_mark: Global ban push complete!")
    
    @sbansync.command(name="syncall")
    @commands.bot_has_permissions(ban_members=True)
    async def sbansyncsyncall(self, ctx: commands.Context):
        """Syncs all bans with all servers in push/pull lists
        
        Yes, this is the fucking help dialog, Infra. *- Infra, but from the past.*"""
        author = ctx.author
        b = self.bot

        pull = await self.config.guild(ctx.guild).allow_pull_from()
        push = await self.config.guild(ctx.guild).allow_push_to()

        async with ctx.typing():
            await ctx.send(f":warning: Commencing global sync.")
            await ctx.send(f":warning: Pulling all global bans from servers...")
            for server in pull:
                await ctx.send(f":inbox_tray: Pulling new bans from server: {b.get_guild(server).name} ({server})")
                try:
                    stats = await self.do_operation(Operation.Pull, author, b.get_guild(server), f"Manual Ban Sync issued by {author} ({author.id})")
                except RuntimeError as e:
                    return await ctx.send(str(e))
                    
                text = ""

                if stats:
                    for k, v in stats.items():
                        text += f"{k} {v}\n"
                else:
                    text = f":ballot_box_with_check: No new bans to pull from {b.get_guild(server).name} ({server})."
                    
                await ctx.send(text)

            await ctx.send(f":warning: Pushing all global bans to servers...")
            for server in push:
                await ctx.send(f":outbox_tray: Pushing new bans to server: {b.get_guild(server).name} ({server})")
                try:
                    stats = await self.do_operation(Operation.Push, author, b.get_guild(server), f"Manual Ban Sync issued by {author} ({author.id})")
                except RuntimeError as e:
                    return await ctx.send(str(e))
                    
                text = ""

                if stats:
                    for k, v in stats.items():
                        text += f"{k} {v}\n"
                else:
                    text = f":ballot_box_with_check: No new bans to push to {b.get_guild(server).name} ({server})."
                    
                await ctx.send(text)

        await ctx.send(":white_check_mark: Global ban sync complete!")

    @commands.group()
    @commands.guild_only()
    @commands.admin()
    async def sbansyncset(self, ctx: commands.Context):
        """SimpleBansync settings"""
        if await self.callout_if_fake_admin(ctx):
            ctx.invoked_subcommand = None

    @sbansyncset.command(name="addpush")
    async def sbansyncsaddpush(self, ctx: commands.Context, *, server: GuildConverter):
        """Allows a server to push bans to this one"""
        async with self.config.guild(ctx.guild).allow_push_to() as allowed_push:
            if server.id not in allowed_push:
                allowed_push.append(server.id)
        await ctx.send(f"`{server.name}` will now be allowed to **push** bans to this server.")


    @sbansyncset.command(name="addpull")
    async def sbansyncsaddpull(self, ctx: commands.Context, *, server: GuildConverter):
        """Allows a server to pull bans from this one"""
        async with self.config.guild(ctx.guild).allow_pull_from() as allowed_pull:
            if server.id not in allowed_pull:
                allowed_pull.append(server.id)
        await ctx.send(f"`{server.name}` will now be allowed to **pull** bans from this server.")

    @sbansyncset.command(name="removepush")
    async def sbansyncsremovepush(self, ctx: commands.Context, *, server: GuildConverter):
        """Disallows a server to push bans to this one"""
        async with self.config.guild(ctx.guild).allow_push_to() as allowed_push:
            if server.id in allowed_push:
                allowed_push.remove(server.id)
        await ctx.send(f"`{server.name}` has been removed from the list of servers allowed to "
                        "**push** bans to this server.")

    @sbansyncset.command(name="removepull")
    async def sbansyncsremovepull(self, ctx: commands.Context, *, server: GuildConverter):
        """Disallows a server to pull bans from this one"""
        async with self.config.guild(ctx.guild).allow_pull_from() as allowed_pull:
            if server.id in allowed_pull:
                allowed_pull.remove(server.id)
        await ctx.send(f"`{server.name}` has been removed from the list of servers allowed to "
                        "**pull** bans from this server.")

    @sbansyncset.command(name="clearpush")
    async def sbansyncsaclearpush(self, ctx: commands.Context):
        """Clears the list of servers allowed to push bans to this one"""
        await self.config.guild(ctx.guild).allow_push_to.clear()
        await ctx.send("Push list cleared. Only local admins are now allowed to push bans to this "
                       "server from elsewhere.")

    @sbansyncset.command(name="clearpull")
    async def sbansyncsclearpull(self, ctx: commands.Context):
        """Clears the list of servers allowed to pull bans from this one"""
        await self.config.guild(ctx.guild).allow_pull_from.clear()
        await ctx.send("Pull list cleared. Only local admins are now allowed to pull bans from this "
                       "server from elsewhere.")

    @sbansyncset.command(name="showlists", aliases=["showsettings"])
    async def sbansyncsshowlists(self, ctx: commands.Context):
        """Shows the current pull and push lists"""
        b = self.bot
        pull = await self.config.guild(ctx.guild).allow_pull_from()
        push = await self.config.guild(ctx.guild).allow_push_to()
        pull = [inline(b.get_guild(s).name) for s in pull if b.get_guild(s)] or ["None"]
        push = [inline(b.get_guild(s).name) for s in push if b.get_guild(s)] or ["None"]

        await ctx.send(f"Pull: {', '.join(pull)}\nPush: {', '.join(push)}")

    async def is_member_allowed(self, operation: Operation, member: discord.Member, target: discord.Guild):
        """A member is allowed to pull, push or sync to a guild if:
            A) Has an admin role in the target server WITH ban permissions
            B) The target server has whitelisted our server for this operation
        """
        target_member = target.get_member(member.id)
        if target_member:
            is_admin_in_target = await self.bot.is_admin(target_member)
            has_ban_perms = target_member.guild_permissions.ban_members
            if is_admin_in_target and has_ban_perms:
                return True

        allow_pull = member.guild.id in await self.config.guild(target).allow_pull_from()
        allow_push = member.guild.id in await self.config.guild(target).allow_push_to()

        if operation == Operation.Pull:
            return allow_pull
        elif operation == Operation.Push:
            return allow_push
        elif operation == Operation.Sync:
            return allow_pull and allow_push
        else:
            raise ValueError("Invalid operation")

    async def do_operation(self, operation: Operation, member: discord.Member, target_guild: discord.Guild, Reason):
        guild = member.guild
        if not target_guild.me.guild_permissions.ban_members:
            raise RuntimeError(":stop_sign: I do not have ban members permissions in the target server.")

        stats = Counter()

        guild_bans = [m.user for m in await guild.bans()]
        target_bans = [m.user for m in await target_guild.bans()]

        if operation in (Operation.Pull, Operation.Sync):
            for m in target_bans:
                if m not in guild_bans:
                    try:
                        await guild.ban(m, delete_message_days=0, reason=Reason)
                    except (discord.Forbidden, discord.HTTPException):
                        stats[":stop_sign: Failed pulls: "] += 1
                    else:
                        stats[":ballot_box_with_check: Pulled bans: "] += 1

        if operation in (Operation.Push, Operation.Sync):
            for m in guild_bans:
                if m not in target_bans:
                    try:
                        await target_guild.ban(m, delete_message_days=0, reason=Reason)
                    except (discord.Forbidden, discord.HTTPException):
                        stats[":stop_sign: Failed pushes: "] += 1
                    else:
                        stats[":ballot_box_with_check: Pushed bans: "] += 1

        return stats

    async def callout_if_fake_admin(self, ctx):
        if ctx.invoked_subcommand is None:
            # User is just checking out the help
            return False
        error_msg = ("It seems that you have a role that is considered admin at bot level but "
                     "not the basic permissions that one would reasonably expect an admin to have.\n"
                     "To use these commands, other than the admin role, you need `administrator` "
                     "permissions OR `ban members`.\n"
                     "I cannot let you proceed until you properly configure permissions in this server.")
        channel = ctx.channel
        has_ban_perms = channel.permissions_for(ctx.author).ban_members

        if not has_ban_perms:
            await ctx.send(error_msg)
            return True
        return False