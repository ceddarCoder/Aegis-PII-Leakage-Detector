# """
# telegram_scraper.py — Scrape public Telegram channels for PII.

# Uses Telethon (MTProto API). Requires API credentials from my.telegram.org.
# Set environment variables:
#     TELEGRAM_API_ID = your_api_id
#     TELEGRAM_API_HASH = your_api_hash
# """

# import os
# import logging
# import asyncio
# from telethon import TelegramClient, errors
# from telethon.errors import ChannelPrivateError, RPCError

# logger = logging.getLogger(__name__)

# API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
# API_HASH = os.getenv("TELEGRAM_API_HASH", "")
# SESSION_FILE = "telegram_session"  # stores login session (will be reused across runs)


# def scrape_telegram_channels(channel_list: list[str], messages_per_channel: int = 50) -> list[dict]:
#     """
#     Synchronous entry point – runs the async scraper in a fresh event loop.
#     Returns a list of message dicts from all channels.
#     """
#     if not API_ID or not API_HASH:
#         raise ValueError(
#             "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment"
#         )

#     async def _scrape_all():
#         """Async function that processes all channels with one client."""
#         client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
#         await client.start()
#         all_messages = []

#         for channel in channel_list:
#             channel = channel.strip()
#             if not channel:
#                 continue
#             # Remove @ if present
#             if channel.startswith("@"):
#                 channel = channel[1:]

#             try:
#                 entity = await client.get_entity(channel)
#                 async for msg in client.iter_messages(entity, limit=messages_per_channel):
#                     if msg.text:
#                         all_messages.append({
#                             "platform": "telegram",
#                             "channel": channel,
#                             "message_id": msg.id,
#                             "content": msg.text,
#                             "date": msg.date.isoformat() if msg.date else "",
#                             "url": f"https://t.me/{channel}/{msg.id}"
#                         })
#             except errors.UsernameNotOccupiedError:
#                 logger.warning("Username '%s' does not exist", channel)
#             except ChannelPrivateError:
#                 logger.warning("Channel %s is private or inaccessible", channel)
#             except RPCError as e:
#                 logger.error("Telegram RPC error for %s: %s", channel, e)
#             except Exception as e:
#                 logger.exception("Unexpected error scraping %s: %s", channel, e)

#         await client.disconnect()
#         return all_messages

#     # Run the async function in a fresh event loop
#     return asyncio.run(_scrape_all())

"""
telegram_scraper.py — Scrape public Telegram channels for PII.
"""

import os
import logging
import asyncio
from telethon import TelegramClient, errors
from telethon.errors import ChannelPrivateError, RPCError
from backend.ocr_engine import get_ocr_engine


logger = logging.getLogger(__name__)

API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_FILE = "telegram_session"


async def scrape_telegram_channels_async(channel_list, messages_per_channel=50, ocr_enabled=False):
    ocr = get_ocr_engine()
    # ... existing code
    if ocr_enabled and msg.photo:
        photo_bytes = await msg.download_media(bytes)
        if photo_bytes:
            ocr_text = await ocr.extract_text_from_bytes_async(photo_bytes)
            if ocr_text:
                all_messages.append({
                    "platform": "telegram",
                    "channel": channel,
                    "message_id": msg.id,
                    "content": ocr_text,
                    "date": msg.date.isoformat() if msg.date else "",
                    "url": f"https://t.me/{channel}/{msg.id}",
                    "content_type": "image_ocr",
                })
    return all_messages

async def scrape_telegram_channels_async(channel_list: list[str], messages_per_channel: int = 50) -> list[dict]:
    """Async version – call this from async endpoints."""
    if not API_ID or not API_HASH:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    all_messages = []

    for channel in channel_list:
        channel = channel.strip()
        if not channel:
            continue
        if channel.startswith("@"):
            channel = channel[1:]

        try:
            entity = await client.get_entity(channel)
            async for msg in client.iter_messages(entity, limit=messages_per_channel):
                if msg.text:
                    all_messages.append({
                        "platform": "telegram",
                        "channel": channel,
                        "message_id": msg.id,
                        "content": msg.text,
                        "date": msg.date.isoformat() if msg.date else "",
                        "url": f"https://t.me/{channel}/{msg.id}"
                    })
        except errors.UsernameNotOccupiedError:
            logger.warning("Username '%s' does not exist", channel)
        except ChannelPrivateError:
            logger.warning("Channel %s is private or inaccessible", channel)
        except RPCError as e:
            logger.error("Telegram RPC error for %s: %s", channel, e)
        except Exception as e:
            logger.exception("Unexpected error scraping %s: %s", channel, e)

    await client.disconnect()
    return all_messages


def scrape_telegram_channels(channel_list: list[str], messages_per_channel: int = 50) -> list[dict]:
    """Synchronous wrapper for non‑async contexts (e.g., Streamlit)."""
    return asyncio.run(scrape_telegram_channels_async(channel_list, messages_per_channel))