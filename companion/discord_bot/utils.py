"""
Utility functions for the Discord bot.
Includes helper functions for user ID extraction, message formatting,
error handling, and rate limiting.
"""
import logging
import discord
from discord import User, Member
from typing import Union, Optional, Dict, Any
import asyncio
import time
from datetime import datetime, timedelta
import re
import aiohttp
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def extract_user_id(author: Union[User, Member]) -> str:
    """
    Extract user ID from Discord User or Member object.
    """
    return str(author.id)


def extract_guild_id(guild: Optional[discord.Guild]) -> Optional[str]:
    """
    Extract guild ID from Discord Guild object.
    """
    return str(guild.id) if guild else None


def format_response(response: str, user: Union[User, Member]) -> str:
    """
    Format the AI's response for Discord presentation.
    This may include applying Discord-specific formatting or user mentions.
    """
    # In basic implementation, just return the response
    # In advanced implementations, you might:
    # - Replace certain keywords with emojis
    # - Format long responses into multiple messages
    # - Add user-specific formatting
    
    # Basic formatting to avoid potential issues with Discord markdown
    formatted_response = response.replace("@everyone", "@ everyone").replace("@here", "@ here")
    
    # Add user mention if needed
    if len(formatted_response) < 1800:  # Discord message limit is 2000, leaving buffer
        return formatted_response
    else:
        # Split long messages if needed
        return split_message_for_discord(formatted_response)


def split_message_for_discord(message: str, max_length: int = 1800) -> str:
    """
    Split a message to fit within Discord's character limit.
    """
    if len(message) <= max_length:
        return message
    
    # For now, just truncate with a note
    # In a more sophisticated implementation, you might split at sentence or paragraph boundaries
    truncated = message[:max_length-50] + "... [Message truncated due to length]"
    return truncated


def handle_error(
    error: Exception,
    context: Optional[Union[discord.ApplicationContext, discord.Message]] = None
) -> str:
    """
    Handle and format Discord bot errors.
    """
    error_msg = f"An error occurred: {str(error)}"
    
    context_str = "unknown"
    if context:
        if hasattr(context, 'command'):
            context_str = f"command:{context.command.name if context.command else 'unknown'}"
        elif hasattr(context, 'channel'):
            context_str = f"channel:{context.channel.id}"
    
    if isinstance(error, discord.DiscordException):
        logger.error(f"Discord error in {context_str}: {error}")
    else:
        logger.error(f"General error in {context_str}: {error}", exc_info=True)
    
    # Return user-friendly error message
    return "Sorry, I encountered an error while processing your request. Please try again later."

async def check_rate_limit(
    redis_client: Redis,
    user_id: str,
    command_name: str,
    limit: int = 5,
    window: int = 60
) -> tuple[bool, str]:
    """
    Check if user is within rate limit for a command using Redis distributed rate limiting.

    Returns (is_allowed, message).

    This implementation uses Redis for distributed, process-safe rate limiting that persists
    across restarts. Uses atomic INCR operations for concurrency safety.

    Args:
        redis_client: Redis async client instance
        user_id: Unique user identifier
        command_name: Name of the command being rate-limited
        limit: Maximum number of requests allowed in the time window
        window: Time window in seconds

    Returns:
        Tuple of (is_allowed: bool, message: str)
        - is_allowed: True if request is within rate limit, False otherwise
        - message: "OK" if allowed, or error message with remaining time if rate limited
    """
    # Build namespaced key for this user+command combination
    rate_limit_key = f"discord:ratelimit:{user_id}:{command_name}"

    try:
        # Use Redis INCR for atomic increment
        current_count = await redis_client.incr(rate_limit_key)

        # If this is the first request, set the expiration window
        if current_count == 1:
            await redis_client.expire(rate_limit_key, window)

        # Check if user has exceeded the limit
        if current_count > limit:
            # Get the remaining TTL to inform user when they can retry
            ttl = await redis_client.ttl(rate_limit_key)

            # Handle edge case where key might have expired between operations
            if ttl == -2:  # Key doesn't exist
                logger.warning(f"Rate limit key expired unexpectedly for {user_id}:{command_name}")
                return True, "OK"
            elif ttl == -1:  # Key exists but has no expiry (shouldn't happen)
                logger.error(f"Rate limit key has no TTL for {user_id}:{command_name}, resetting")
                await redis_client.delete(rate_limit_key)
                return True, "OK"

            return False, f"Rate limit exceeded. Try again in {ttl} seconds."

        return True, "OK"

    except Exception as e:
        # Graceful degradation: if Redis fails, log error and allow the request
        # This prevents Redis outages from completely blocking bot functionality
        logger.error(f"Redis error during rate limit check for {user_id}:{command_name}: {e}", exc_info=True)
        return True, "OK (rate limiting temporarily unavailable)"


def setup_logging():
    """
    Setup logging for the Discord bot.
    """
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def validate_discord_token(token: str) -> bool:
    """
    Basic validation of Discord bot token format.
    Discord tokens have format: [ID].[Timestamp].[HMAC]
    Each part is base64-encoded (alphanumeric, underscores, hyphens).
    """
    import base64
    
    if not token:
        return False

    # Discord bot token format: [Base64 ID].[Base64 Timestamp].[Base64 HMAC]
    # Example: <REDACTED_TOKEN_EXAMPLE>
    parts = token.split('.')
    if len(parts) != 3:
        return False

    # Each part should be non-empty and contain only valid base64 characters
    # Each part should be non-empty and contain only valid base64 characters
    for part in parts:
        if not part or not re.match(r'^[A-Za-z0-9_-]+$', part):
            return False
    if len(parts[0]) < 10 or len(parts[1]) < 6 or len(parts[2]) < 6:
        return False

    return True

async def send_safe_message(channel: discord.TextChannel, content: str, **kwargs) -> Optional[discord.Message]:
    """
    Safely send a message to a Discord channel with error handling.
    """
    try:
        # Ensure content is within Discord limits
        if len(content) > 2000:
            content = content[:1995] + "... [truncated]"
        
        return await channel.send(content, **kwargs)
    except discord.HTTPException as e:
        logger.error(f"Failed to send message to channel {channel.id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error sending message to channel {channel.id}: {e}")
        return None


async def wait_for_user_response(bot, channel: discord.TextChannel, user: discord.User, timeout: int = 60) -> Optional[discord.Message]:
    """
    Wait for a response from a specific user in a specific channel.
    """
    def check(message):
        return message.author.id == user.id and message.channel.id == channel.id
    
    try:
        response = await bot.wait_for('message', check=check, timeout=timeout)
        return response
    except asyncio.TimeoutError:
        await channel.send("Timed out waiting for your response.")
        return None


def format_timestamp(timestamp: datetime) -> str:
    """
    Format datetime for Discord display.
    """
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def extract_discord_mentions(text: str) -> list[str]:
    """
    Extract Discord user mentions from text.
    """
    # Pattern to match <@user_id> or <@!user_id> (with nickname)
    mention_pattern = r'<@!?(\d+)>'
    user_ids = re.findall(mention_pattern, text)
    return user_ids


def is_valid_discord_id(id_str: str) -> bool:
    """
    Check if a string is a valid Discord ID (18-19 digits).
    """
    return bool(re.match(r'^\d{18,19}$', id_str))


def sanitize_for_discord(text: str) -> str:
    """
    Sanitize text for safe use in Discord.
    Breaks mentions and role pings using zero-width space to prevent unwanted notifications.
    """
    # Prevent mentioning @everyone and @here
    text = text.replace('@everyone', '@ everyone')
    text = text.replace('@here', '@ here')

    # Break user mentions with zero-width space (prevents pings)
    text = re.sub(r'<@!?(\d+)>', lambda m: f'<@\u200b{m.group(1)}>', text)

    # Break role mentions with zero-width space (prevents role pings)
    text = re.sub(r'<@&(\d+)>', lambda m: f'<@&\u200b{m.group(1)}>', text)

    return text


def get_user_avatar_url(user: Union[User, Member]) -> Optional[str]:
    """
    Get the user's avatar URL.
    """
    try:
        return str(user.avatar.url) if user.avatar else str(user.default_avatar.url)
    except Exception:
        return None

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable format.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


async def bulk_delete_messages(channel: discord.TextChannel, count: int, check_func=None):
    """
    Bulk delete messages from a channel with optional filter.
    """
    try:
        def default_check(msg):
            return not msg.pinned
        
        check = check_func or default_check
        deleted = await channel.purge(limit=count, check=check)
        return len(deleted)
    except discord.Forbidden:
        logger.warning(f"Bot doesn't have permission to delete messages in channel {channel.id}")
        return 0
        return False

    return True


async def send_safe_message(channel: discord.TextChannel, content: str, **kwargs) -> Optional[discord.Message]:
    """
    Safely send a message to a Discord channel with error handling.
    """
    try:
        # Ensure content is within Discord limits
        if len(content) > 2000:
            content = content[:1995] + "... [truncated]"
        
        return await channel.send(content, **kwargs)
    except discord.HTTPException as e:
        logger.error(f"Failed to send message to channel {channel.id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error sending message to channel {channel.id}: {e}")
        return None


async def wait_for_user_response(bot, channel: discord.TextChannel, user: discord.User, timeout: int = 60) -> Optional[discord.Message]:
    """
    Wait for a response from a specific user in a specific channel.
    """
    def check(message):
        return message.author.id == user.id and message.channel.id == channel.id
    
    try:
        response = await bot.wait_for('message', check=check, timeout=timeout)
        return response
    except asyncio.TimeoutError:
        await channel.send("Timed out waiting for your response.")
        return None


def format_timestamp(timestamp: datetime) -> str:
    """
    Format datetime for Discord display.
    """
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def extract_discord_mentions(text: str) -> list[str]:
    """
    Extract Discord user mentions from text.
    """
    # Pattern to match <@user_id> or <@!user_id> (with nickname)
    mention_pattern = r'<@!?(\d+)>'
    user_ids = re.findall(mention_pattern, text)
    return user_ids


def is_valid_discord_id(id_str: str) -> bool:
    """
    Check if a string is a valid Discord ID (18-19 digits).
    """
    return bool(re.match(r'^\d{18,19}$', id_str))


def sanitize_for_discord(text: str) -> str:
    """
    Sanitize text for safe use in Discord.
    Breaks mentions and role pings using zero-width space to prevent unwanted notifications.
    """
    # Prevent mentioning @everyone and @here
    text = text.replace('@everyone', '@ everyone')
    text = text.replace('@here', '@ here')

    # Break user mentions with zero-width space (prevents pings)
    text = re.sub(r'<@!?(\d+)>', lambda m: f'<@\u200b{m.group(1)}>', text)

    # Break role mentions with zero-width space (prevents role pings)
    text = re.sub(r'<@&(\d+)>', lambda m: f'<@&\u200b{m.group(1)}>', text)

    return text


def get_user_avatar_url(user: Union[User, Member]) -> Optional[str]:
    """
    Get the user's avatar URL.
    """
    try:
        return str(user.avatar.url) if user.avatar else str(user.default_avatar.url)
    except Exception:
        return None

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable format.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


async def bulk_delete_messages(channel: discord.TextChannel, count: int, check_func=None):
    """
    Bulk delete messages from a channel with optional filter.
    """
    try:
        def default_check(msg):
            return not msg.pinned
        
        check = check_func or default_check
        deleted = await channel.purge(limit=count, check=check)
        return len(deleted)
    except discord.Forbidden:
        logger.warning(f"Bot doesn't have permission to delete messages in channel {channel.id}")
        return 0
    except Exception as e:
        logger.error(f"Error bulk deleting messages in channel {channel.id}: {e}")
        return 0