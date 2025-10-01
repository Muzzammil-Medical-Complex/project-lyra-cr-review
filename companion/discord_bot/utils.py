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


async def handle_error(error: Exception, context: Optional[Union[discord.ApplicationContext, discord.Message]] = None) -> str:
    """
    Handle and format Discord bot errors.
    """
    error_msg = f"An error occurred: {str(error)}"
    
    if isinstance(error, discord.DiscordException):
        logger.error(f"Discord error in {'context' if context else 'unknown'}: {error}")
    else:
        logger.error(f"General error in {'context' if context else 'unknown'}: {error}", exc_info=True)
    
    # Return user-friendly error message
    return "Sorry, I encountered an error while processing your request. Please try again later."


async def check_rate_limit(user_id: str, command_name: str, limit: int = 5, window: int = 60) -> tuple[bool, str]:
    """
    Check if user is within rate limit for a command.
    Returns (is_allowed, message).
    """
    # This is a simplified rate limiting implementation
    # In a production system, you'd likely use Redis or similar for distributed rate limiting
    current_time = time.time()
    
    # For simplicity, we'll store rate limit info in memory (not suitable for production with multiple instances)
    if not hasattr(check_rate_limit, 'rate_limits'):
        check_rate_limit.rate_limits = {}
    
    user_key = f"{user_id}:{command_name}"
    
    if user_key not in check_rate_limit.rate_limits:
        check_rate_limit.rate_limits[user_key] = []
    
    # Clean old entries
    check_rate_limit.rate_limits[user_key] = [
        timestamp for timestamp in check_rate_limit.rate_limits[user_key] 
        if current_time - timestamp < window
    ]
    
    # Check if over limit
    if len(check_rate_limit.rate_limits[user_key]) >= limit:
        time_remaining = window - (current_time - check_rate_limit.rate_limits[user_key][0])
        return False, f"Rate limit exceeded. Try again in {int(time_remaining)} seconds."
    
    # Add current timestamp
    check_rate_limit.rate_limits[user_key].append(current_time)
    
    return True, "OK"


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
    if not token:
        return False

    # Discord bot token format: [Base64 ID].[Base64 Timestamp].[Base64 HMAC]
    # Example: <REDACTED_TOKEN_EXAMPLE>
    parts = token.split('.')
    if len(parts) != 3:
        return False

    # Each part should be non-empty and contain only valid base64 characters
    for part in parts:
        if not part or not re.match(r'^[A-Za-z0-9_-]+$', part):
            return False

    # First part (ID) should be at least 10 characters
    # Last two parts should be at least 6 characters each
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
    """
    # Prevent mentioning @everyone and @here
    text = text.replace('@everyone', '@ everyone')
    text = text.replace('@here', '@ here')
    
    # Escape any existing mentions
    text = re.sub(r'<@!?(\d+)>', r'<@\1>', text)  # This keeps the mention but makes it less problematic
    
    return text


async def get_user_avatar_url(user: Union[User, Member]) -> Optional[str]:
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