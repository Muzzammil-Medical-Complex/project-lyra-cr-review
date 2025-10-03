"""
Discord slash commands for the AI Companion System.
Defines commands like /companion, /memories, /personality and handles their interaction with the gateway API.
"""
import discord
from discord import option
from discord.ext import commands
import asyncio
import aiohttp
import logging
from typing import Optional, List
import json
from datetime import datetime

from .utils import (
    extract_user_id, format_response, handle_error, 
    check_rate_limit, sanitize_for_discord, format_duration
)

logger = logging.getLogger(__name__)


class CompanionCommands(commands.Cog):
    def __init__(self, bot, gateway_url: str = "http://gateway:8000"):
        self.bot = bot
        self.gateway_url = gateway_url
        self.session = None
        self.user_locks = {}  # Prevent concurrent processing per user

    async def cog_before_invoke(self, _ctx):
        """Ensure an aiohttp session exists before each command"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.session and not self.session.closed:
            await self.session.close()

    @discord.slash_command(
        name="companion",
        description="Chat with your AI companion"
    )
    @option("message", str, description="Your message to the AI companion", required=True)
    async def companion_chat(self, ctx: discord.ApplicationContext, message: str):
        """
        Main command for chatting with the AI companion.
        Sends the message to the gateway API and returns the response.
        """
        user_id = extract_user_id(ctx.author)

        # Check rate limit (use bot's redis_client for distributed rate limiting)
        if self.bot.redis_client:
            allowed, rate_limit_msg = await check_rate_limit(self.bot.redis_client, user_id, "companion_chat")
            if not allowed:
                await ctx.respond(rate_limit_msg, ephemeral=True)
                return
        
        # Get or create lock for this user atomically
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        lock = self.user_locks[user_id]

        # Try to acquire lock non-blocking
        if lock.locked():
            await ctx.respond("Please wait, I'm still processing your previous message...", ephemeral=True)
            return

        # Acquire lock and process request
        async with lock:
            try:
                await ctx.defer(ephemeral=False)

                # Prepare request to gateway (include user_id in session to avoid collisions)
                chat_request = {
                    "user_id": user_id,
                    "message": message,
                    "session_id": f"discord_{user_id}_{ctx.channel.id}",
                    "message_id": str(ctx.interaction.id)
                }

                # Call gateway API
                response = await self._call_gateway_api(
                    f"{self.gateway_url}/chat/message",
                    chat_request
                )

                if response:
                    agent_response = response.get("agent_response", "I couldn't process that request.")
                    formatted_response = format_response(agent_response, ctx.author)

                    await ctx.respond(formatted_response)
                    logger.info(f"Companion chat processed for user {user_id}")
                else:
                    await ctx.respond("Sorry, I'm having trouble connecting to my brain right now. Please try again later.", ephemeral=True)

            except Exception as e:
                error_msg = handle_error(e, ctx)
                await ctx.respond(error_msg, ephemeral=True)

    @discord.slash_command(
        name="personality",
        description="View your AI companion's current personality state"
    )
    async def view_personality(self, ctx: discord.ApplicationContext):
        """
        Command to view the current personality state of the user's AI companion.
        """
        user_id = extract_user_id(ctx.author)

        # Check rate limit (use bot's redis_client for distributed rate limiting)
        if self.bot.redis_client:
            allowed, rate_limit_msg = await check_rate_limit(self.bot.redis_client, user_id, "personality")
            if not allowed:
                await ctx.respond(rate_limit_msg, ephemeral=True)
                return
        
        try:
            await ctx.defer(ephemeral=True)
            
            # Call gateway API to get personality
            personality_data = await self._call_gateway_api(
                f"{self.gateway_url}/personality/current/{user_id}"
            )
            
            if personality_data:
                # Extract personality metrics
                current_pad = personality_data.get("current_pad") or {}
                big_five = personality_data.get("big_five", {})
                
                if big_five:
                    embed = discord.Embed(
                        title="Your AI Companion's Personality",
                        description=f"Current Emotional State: {current_pad.get('emotion_label', 'Unknown')}",
                        color=0x7289da
                    )
                    
                    # Add Big Five traits
                    embed.add_field(
                        name="Big Five Traits (Fixed)",
                        value=f"""
                        Openness: {big_five.get('openness', 0):.2f}
                        Conscientiousness: {big_five.get('conscientiousness', 0):.2f}
                        Extraversion: {big_five.get('extraversion', 0):.2f}
                        Agreeableness: {big_five.get('agreeableness', 0):.2f}
                        Neuroticism: {big_five.get('neuroticism', 0):.2f}
                        """,
                        inline=False
                    )
                    
                    # Add current PAD state
                    if current_pad:
                        embed.add_field(
                            name="Current Emotional State (PAD)",
                            value=f"""
                            Pleasure: {current_pad.get('pleasure', 0):.2f}
                            Arousal: {current_pad.get('arousal', 0):.2f}
                            Dominance: {current_pad.get('dominance', 0):.2f}
                            """,
                            inline=True
                        )
                    
                    # Add quirks if available
                    active_quirks = personality_data.get("active_quirks", [])
                    if active_quirks:
                        quirks_text = "\n".join([
                            f"• {q['name']} (strength: {q['strength']:.2f})" 
                            for q in active_quirks[:5]  # Limit to first 5 quirks
                        ])
                        if len(active_quirks) > 5:
                            quirks_text += f"\n... and {len(active_quirks) - 5} more"
                        
                        embed.add_field(
                            name=f"Active Quirks ({len(active_quirks)})",
                            value=quirks_text,
                            inline=False
                        )
                    
                    embed.timestamp = datetime.utcnow()
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("Personality data not available.", ephemeral=True)
            else:
                await ctx.respond("Could not retrieve personality data. Please try again later.", ephemeral=True)
                
        except Exception as e:
            error_msg = handle_error(e, ctx)
            await ctx.respond(error_msg, ephemeral=True)

    @discord.slash_command(
        name="memories",
        description="Search and view your AI companion's memories of your conversations"
    )
    @option("query", str, description="What would you like to search for in memories?", required=False)
    @option("limit", int, description="Number of memories to return (1-10)", required=False, default=5, min_value=1, max_value=10)
    async def view_memories(self, ctx: discord.ApplicationContext, query: Optional[str] = None, limit: Optional[int] = 5):
        """
        Command to search and view memories stored about the user.
        """
        user_id = extract_user_id(ctx.author)

        # Check rate limit (use bot's redis_client for distributed rate limiting)
        if self.bot.redis_client:
            allowed, rate_limit_msg = await check_rate_limit(self.bot.redis_client, user_id, "memories")
            if not allowed:
                await ctx.respond(rate_limit_msg, ephemeral=True)
                return
        
        try:
            await ctx.defer(ephemeral=True)
            
            # Prepare search query
            if query:
                search_query = {
                    "text": query,
                    "k": limit,
                    "memory_type": "episodic"  # Focus on episodic memories for conversations
                }
                
                # Call gateway API to search memories
                memories = await self._call_gateway_api(
                    f"{self.gateway_url}/memory/search/{user_id}",
                    search_query,
                    method="POST"
                )
            else:
                # Just get recent memories
                memories = await self._call_gateway_api(
                    f"{self.gateway_url}/memory/episodic/{user_id}?limit={limit}&offset=0"
                )
            
            if memories:
                embed = discord.Embed(
                    title="Your Conversation Memories",
                    description=f"Found {len(memories)} memory(ies)" if memories else "No memories found",
                    color=0x7289da
                )
                
                # Add each memory as a field (limit to first 5 to avoid embed limits)
                for i, memory in enumerate(memories[:5]):
                    content_preview = memory.get('content', '')[:100] + "..." if len(memory.get('content', '')) > 100 else memory.get('content', '')
                    importance = memory.get('importance_score', 0)
                    
                    embed.add_field(
                        name=f"Memory {i+1} (Score: {importance:.2f})",
                        value=content_preview,
                        inline=False
                    )
                
                if len(memories) > 5:
                    embed.set_footer(text=f"Showing first 5 of {len(memories)} memories")
                
                embed.timestamp = datetime.utcnow()
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No memories found for your query.", ephemeral=True)
                
        except Exception as e:
            error_msg = handle_error(e, ctx)
            await ctx.respond(error_msg, ephemeral=True)

    @discord.slash_command(
        name="needs",
        description="View your AI companion's current psychological needs"
    )
    async def view_needs(self, ctx: discord.ApplicationContext):
        """
        Command to view the current psychological needs of the AI companion.
        """
        user_id = extract_user_id(ctx.author)

        # Check rate limit (use bot's redis_client for distributed rate limiting)
        if self.bot.redis_client:
            allowed, rate_limit_msg = await check_rate_limit(self.bot.redis_client, user_id, "needs")
            if not allowed:
                await ctx.respond(rate_limit_msg, ephemeral=True)
                return
        
        try:
            await ctx.defer(ephemeral=True)
            
            # Call gateway API to get user needs
            needs_data = await self._call_gateway_api(
                f"{self.gateway_url}/personality/needs/{user_id}"
            )
            
            if needs_data:
                embed = discord.Embed(
                    title="Your AI Companion's Psychological Needs",
                    color=0x7289da
                )
                
                urgent_needs = []
                for need in needs_data:
                    need_type = need['need_type']
                    current_level = need['current_level']
                    baseline_level = need['baseline_level']
                    trigger_threshold = need['trigger_threshold']
                    
                    # Add indicator for urgent needs
                    is_urgent = current_level >= trigger_threshold
                    urgent_indicator = " 🔥" if is_urgent else ""
                    
                    embed.add_field(
                        name=f"{need_type.title()}{urgent_indicator}",
                        value=f"""
                        Current: {current_level:.2f}
                        Baseline: {baseline_level:.2f}
                        Threshold: {trigger_threshold:.2f}
                        """,
                        inline=True
                    )
                    
                    if is_urgent:
                        urgent_needs.append(need_type)
                
                if urgent_needs:
                    embed.description = f"⚠️ **Urgent Needs:** {', '.join(urgent_needs)} are high and may trigger proactive conversations"
                
                embed.timestamp = datetime.utcnow()
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Could not retrieve needs data. Please try again later.", ephemeral=True)
                
        except Exception as e:
            error_msg = handle_error(e, ctx)
            await ctx.respond(error_msg, ephemeral=True)

    @discord.slash_command(
        name="stats",
        description="View your usage statistics with the AI companion"
    )
    async def view_stats(self, ctx: discord.ApplicationContext):
        """
        Command to view usage statistics for the user.
        """
        user_id = extract_user_id(ctx.author)

        # Check rate limit (use bot's redis_client for distributed rate limiting)
        if self.bot.redis_client:
            allowed, rate_limit_msg = await check_rate_limit(self.bot.redis_client, user_id, "stats")
            if not allowed:
                await ctx.respond(rate_limit_msg, ephemeral=True)
                return
        
        try:
            await ctx.defer(ephemeral=True)
            
            # Call gateway API to get user profile/stats (proper endpoint, not admin)
            user_profile = await self._call_gateway_api(
                f"{self.gateway_url}/users/{user_id}"
            )
            
            if user_profile:
                embed = discord.Embed(
                    title="Your Companion Statistics",
                    color=0x7289da
                )
                
                # Add various stats
                embed.add_field(
                    name="Interactions",
                    value=user_profile.get('total_interactions', 0),
                    inline=True
                )
                
                embed.add_field(
                    name="Memories Stored",
                    value=user_profile.get('memory_count', 0),
                    inline=True
                )
                
                # Add last active info
                last_active = user_profile.get('last_active')
                if last_active:
                    embed.add_field(
                        name="Last Active",
                        value=last_active,
                        inline=True
                    )
                
                # Add account creation date
                created_at = user_profile.get('created_at')
                if created_at:
                    embed.add_field(
                        name="Account Created",
                        value=created_at,
                        inline=True
                    )
                
                embed.timestamp = datetime.utcnow()
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Could not retrieve your statistics. Please try again later.", ephemeral=True)
                
        except Exception as e:
            error_msg = handle_error(e, ctx)
            await ctx.respond(error_msg, ephemeral=True)

    async def _call_gateway_api(self, url: str, data: Optional[dict] = None, method: str = "GET"):
        """
        Helper method to call the gateway API.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            
            if method.upper() == "POST":
                async with self.session.post(url, json=data, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Gateway API error: {response.status} - {await response.text()}")
                        return None
            else:
                async with self.session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Gateway API error: {response.status} - {await response.text()}")
                        return None
        except asyncio.TimeoutError:
            logger.exception(f"Gateway API timeout for URL: {url}")
            return None
        except Exception as e:
            logger.exception(f"Gateway API error for URL {url}: {e}")
            return None

    @commands.command(name="ping")
    async def ping(self, ctx):
        """
        Ping command to check if bot is responsive.
        """
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency}ms")


def setup(bot, gateway_url: str = "http://gateway:8000"):
    """
    Setup function to add the commands cog to the bot.
    """
    bot.add_cog(CompanionCommands(bot, gateway_url))
    logger.info(f"CompanionCommands cog loaded with gateway URL: {gateway_url}")