"""
Main Discord bot for the AI Companion System.
Handles message events, manages user locks, and contains proactive messaging entry point.
"""
import discord
from discord.ext import commands, tasks
import asyncio
import logging
import os
import sys
from typing import Dict, Set, Optional
import aiohttp
import json
from datetime import datetime

from .utils import (
    extract_user_id, format_response, handle_error, 
    setup_logging, validate_discord_token
)
from .commands import setup as setup_commands


class CompanionBot(commands.Bot):
    def __init__(self, gateway_url: str = "http://gateway:8000"):
        # Set up intents - we need message content, members, and other relevant events
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        intents.members = True  # Required to access member information
        intents.guilds = True  # Required to access guild information
        
        # Initialize the bot with intents
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None  # Disable default help command since we use slash commands
        )
        
        self.gateway_url = gateway_url
        self.user_locks: Dict[str, bool] = {}  # Prevent concurrent processing per user
        self.user_sessions: Dict[str, str] = {}  # Track conversation sessions by user
        self.active_guilds: Set[int] = set()  # Track guilds where bot is active
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Setup logging
        setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Proactive messaging queue
        self.proactive_queue = asyncio.Queue()

    async def setup_hook(self):
        """Async setup method called when the bot is starting up."""
        self.logger.info("Setting up CompanionBot...")
        
        # Create aiohttp session
        self.session = aiohttp.ClientSession()
        
        # Setup commands (slash commands)
        setup_commands(self, self.gateway_url)
        
        # Sync slash commands globally (or per guild if preferred)
        try:
            await self.sync_commands()
            self.logger.info("Slash commands synchronized")
        except Exception as e:
            self.logger.error(f"Error syncing commands: {e}")
        
        # Start proactive message processor
        self.process_proactive_messages.start()
        
        self.logger.info("CompanionBot setup complete")

    async def on_connect(self):
        """Called when the bot successfully connects to Discord."""
        self.logger.info(f"Bot connected as {self.user}")

    async def on_ready(self):
        """Called when the bot is ready and logged in."""
        self.logger.info(f"Bot {self.user} is ready! | {len(self.guilds)} guilds | {len(self.users)} users")
        
        # Track active guilds
        self.active_guilds = {guild.id for guild in self.guilds}
        
        # Update presence
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Conversations & Friendships")
        )

    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild."""
        self.logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        self.active_guilds.add(guild.id)

    async def on_guild_remove(self, guild):
        """Called when the bot leaves a guild."""
        self.logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        self.active_guilds.discard(guild.id)

    async def on_message(self, message):
        """
        Handle incoming messages.
        """
        # Ignore messages from bots, including this bot
        if message.author.bot:
            return

        # Check if this is a DM or in a server where the bot should respond
        if isinstance(message.channel, discord.DMChannel) or message.guild is not None:
            # Extract user ID
            user_id = extract_user_id(message.author)
            
            # Check for user lock to prevent concurrent processing
            if user_id in self.user_locks:
                # Send a temporary response if user is already being processed
                await message.add_reaction("⏳")
                return
            
            # Acquire user lock
            self.user_locks[user_id] = True
            
            try:
                # Process the message via gateway API
                await self._process_message_via_gateway(message)
            except Exception as e:
                error_msg = await handle_error(e, message)
                await message.channel.send(error_msg)
            finally:
                # Release user lock
                if user_id in self.user_locks:
                    del self.user_locks[user_id]
                    
                # Remove any temporary reactions
                try:
                    await message.clear_reactions()
                except:
                    pass  # Ignore if we can't clear reactions

    async def _process_message_via_gateway(self, message: discord.Message):
        """
        Send message to gateway API and return response.
        """
        user_id = extract_user_id(message.author)
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Prepare request to gateway
                chat_request = {
                    "user_id": user_id,
                    "message": message.content,
                    "session_id": self.user_sessions.get(user_id, f"discord_{message.channel.id}"),
                    "message_id": str(message.id)
                }
                
                # Call gateway API
                async with self.session.post(
                    f"{self.gateway_url}/chat/message", 
                    json=chat_request,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        agent_response = result.get("agent_response", "I couldn't process that request.")
                        
                        # Format and send response
                        formatted_response = format_response(agent_response, message.author)
                        await message.reply(formatted_response)
                        
                        # Update session ID if new one was provided
                        if result.get("session_id"):
                            self.user_sessions[user_id] = result["session_id"]
                        
                        self.logger.info(f"Processed message for user {user_id}")
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Gateway API error: {response.status} - {error_text}")
                        await message.reply("Sorry, I'm having trouble connecting to my brain right now. Please try again later.")
                        
            except asyncio.TimeoutError:
                await message.reply("Sorry, the response is taking too long. Please try again.")
            except Exception as e:
                self.logger.error(f"Error processing message via gateway: {e}")
                await message.reply("An error occurred while processing your message.")

    async def send_proactive_message(self, user_id: str, content: str, trigger_reason: str = "system"):
        """
        Called by gateway for proactive conversations.
        Adds the message to the proactive queue for processing.
        """
        await self.proactive_queue.put({
            "user_id": user_id,
            "content": content,
            "trigger_reason": trigger_reason,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.logger.info(f"Added proactive message to queue for user {user_id}")

    @tasks.loop(seconds=2)  # Process proactive messages every 2 seconds
    async def process_proactive_messages(self):
        """
        Background task to process proactive messages from the queue.
        """
        if self.proactive_queue.empty():
            return
            
        try:
            # Get proactive message info from queue
            msg_info = await self.proactive_queue.get()
            
            user_id = msg_info["user_id"]
            content = msg_info["content"]
            trigger_reason = msg_info["trigger_reason"]
            
            # Find the user
            user = self.get_user(int(user_id))
            if not user:
                # If we can't find the user in cache, try to fetch them
                try:
                    user = await self.fetch_user(int(user_id))
                except discord.NotFound:
                    self.logger.warning(f"Could not find user {user_id} for proactive message")
                    return
            
            # Check if user has proactive messaging enabled
            # In a real implementation, you'd check this via the gateway API
            # For now, we'll assume it's enabled
            
            # Check rate limits and user locks
            if user_id in self.user_locks:
                # If user is currently being processed, wait and requeue
                await self.proactive_queue.put(msg_info)
                await asyncio.sleep(5)  # Wait 5 seconds before reattempting
                return
            
            # Send proactive message
            try:
                # Try to send as DM first
                await user.send(f"🔔 **Proactive Message** ({trigger_reason}): {content}")
                self.logger.info(f"Sent proactive message to user {user_id}")
            except discord.Forbidden:
                # If DM is not allowed, try to send in their last known channel
                self.logger.warning(f"Could not DM user {user_id}, trying last known channel")
                # In a complete implementation, you would store the last known channel
                # and attempt to send the message there with a @mention
                # For now, we'll just log that we couldn't send it
                self.logger.warning(f"Could not send proactive message to user {user_id} - DM forbidden and no fallback channel")
            
        except Exception as e:
            self.logger.error(f"Error processing proactive message: {e}")

    def get_user_by_id(self, user_id: str) -> Optional[discord.User]:
        """
        Get a user by their ID.
        """
        return self.get_user(int(user_id))

    async def get_or_create_user_profile(self, user_id: str) -> Dict:
        """
        Get or create a user profile via gateway API.
        """
        try:
            # First try to get existing profile
            async with self.session.get(f"{self.gateway_url}/admin/users?user_id={user_id}") as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    # User doesn't exist, create new profile
                    new_profile_data = {
                        "user_id": user_id,
                        "discord_username": self.get_user(int(user_id)).name if self.get_user(int(user_id)) else "Unknown",
                        "status": "active",
                        "initialization_completed": False,
                        "personality_initialized": False
                    }
                    
                    async with self.session.post(
                        f"{self.gateway_url}/admin/users", 
                        json=new_profile_data
                    ) as create_response:
                        if create_response.status in [200, 201]:
                            return await create_response.json()
                        else:
                            self.logger.error(f"Could not create user profile: {create_response.status}")
                            return {}
                else:
                    self.logger.error(f"Could not get user profile: {response.status}")
                    return {}
        except Exception as e:
            self.logger.error(f"Error getting/creating user profile: {e}")
            return {}

    async def close(self):
        """
        Cleanup when bot is shutting down.
        """
        self.logger.info("Shutting down CompanionBot...")
        
        # Stop background tasks
        self.process_proactive_messages.cancel()
        
        # Close aiohttp session
        if self.session and not self.session.closed:
            await self.session.close()
        
        # Release all user locks
        self.user_locks.clear()
        
        await super().close()
        self.logger.info("CompanionBot shutdown complete")

    async def on_disconnect(self):
        """Called when the bot disconnects from Discord."""
        self.logger.info("Bot disconnected from Discord")

    async def on_resumed(self):
        """Called when the bot resumes connection to Discord."""
        self.logger.info("Bot resumed connection to Discord")

    async def on_error(self, event_method, *args, **kwargs):
        """
        Handle any uncaught errors in the bot.
        """
        self.logger.error(f"Error in {event_method}: {sys.exc_info()}")
        
        # Log the full traceback
        import traceback
        traceback.print_exc()


async def run_discord_bot(token: str, gateway_url: str = "http://gateway:8000"):
    """
    Run the Discord bot with the provided token.
    """
    if not validate_discord_token(token):
        raise ValueError("Invalid Discord bot token provided")
    
    bot = CompanionBot(gateway_url=gateway_url)
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        await bot.close()
    except Exception as e:
        print(f"Error running Discord bot: {e}")
        raise


if __name__ == "__main__":
    # Get token from environment variable
    DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
    
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    # Run the bot
    asyncio.run(run_discord_bot(DISCORD_TOKEN, GATEWAY_URL))