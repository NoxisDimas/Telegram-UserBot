import asyncio
import random
import os
from datetime import datetime, timezone
from telethon import events, TelegramClient
from telethon.errors import FloodWaitError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Global kill switch flag
SCRAPE_ACTIVE = True

async def setup_scraper(client: TelegramClient):
    """
    Sets up event handlers for scraping media.
    """
    
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stopscrape(?: |$)"))
    async def stop_scrape_handler(event):
        global SCRAPE_ACTIVE
        SCRAPE_ACTIVE = False
        await event.edit("🛑 **Kill switch diaktifkan! Proses scraping akan segera dihentikan.**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.scrapemedia(?: |$)(.*)"))
    async def scrape_media_handler(event):
        global SCRAPE_ACTIVE
        SCRAPE_ACTIVE = True
        args_str = event.pattern_match.group(1).strip()
        if not args_str:
            await event.edit("❌ **Penggunaan:** `.scrapemedia <chat_id> <limit> [YYYY-MM-DD]`")
            return
            
        args = args_str.split()
        if len(args) < 2:
            await event.edit("❌ **Penggunaan:** `.scrapemedia <chat_id> <limit> [YYYY-MM-DD]`\nContoh: `.scrapemedia -100123456 10`")
            return
            
        chat_id_raw = args[0]
        try:
            limit = int(args[1])
        except ValueError:
            await event.edit("❌ **Error:** `<limit>` harus berupa angka (integer).")
            return

        date_offset = None
        if len(args) >= 3:
            try:
                date_str = args[2]
                # Parse date to datetime
                date_offset = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                await event.edit("❌ **Error:** Format tanggal harus `YYYY-MM-DD`.")
                return

        # Parsing chat_id yang lebih canggih (mendukung link)
        chat_id_raw = chat_id_raw.strip()
        import re
        private_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/c/(\d+)', chat_id_raw)
        if private_match:
            chat_id = int(f"-100{private_match.group(1)}")
        else:
            public_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)', chat_id_raw)
            if public_match:
                chat_id = public_match.group(1)
            else:
                if chat_id_raw.lstrip('-').isdigit():
                    chat_id = int(chat_id_raw)
                else:
                    chat_id = chat_id_raw
                    
        # Ambil entity terlebih dahulu agar iter_messages tidak gagal
        try:
            entity = await client.get_entity(chat_id)
            chat_id = entity
        except Exception as e:
            await event.edit(f"❌ **Error:** Tidak dapat menemukan channel/grup tersebut.\nPastikan ID/Username/Link benar atau bot sudah pernah bergabung/melihat chat tersebut.\nDetail: `{str(e)}`")
            return
            
        date_display = date_offset.strftime('%Y-%m-%d') if date_offset else 'Terbaru'
        status_msg = await event.edit(
            f"⏳ **Scraping dimulai...**\n"
            f"Target: `{chat_id.id}`\n"
            f"Target Jumlah Media: `{limit}`\n"
            f"Mulai dari Tanggal: `{date_display}` (Mundur)\n\n"
            f"Mohon tunggu, proses berjalan di latar belakang..."
        )
        
        import tempfile
        temp_dir = os.path.join(tempfile.gettempdir(), "userbot_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Run background task
        asyncio.create_task(run_scrape_task(client, status_msg, chat_id, limit, date_offset, temp_dir))

async def run_scrape_task(client: TelegramClient, status_msg, chat_id, limit, date_offset, temp_dir):
    try:
        count = 0
        saved_count = 0
        error_count = 0
        last_error = ""
        
        kwargs = {}
        if date_offset:
            # offset_date fetches messages older than (or equal to) this date
            kwargs["offset_date"] = date_offset
            
        async for message in client.iter_messages(chat_id, **kwargs):
            if not SCRAPE_ACTIVE:
                await status_msg.edit(
                    f"🛑 **Scraping Dihentikan (Kill Switch)!**\n"
                    f"Berhasil Disimpan: `{saved_count}`\n"
                    f"Gagal: `{error_count}`"
                )
                logger.info("Scraping task aborted by kill switch")
                return

            if not message.media:
                continue
                
            count += 1
            
            try:
                # Langsung download media dan kirim (tanpa forward) sesuai permintaan
                file_path = await message.download_media(file=temp_dir + "/")
                if file_path:
                    # Truncate caption if too long to prevent MediaCaptionTooLongError
                    cap = message.message or ""
                    if len(cap) > 1000:
                        cap = cap[:1000] + "..."
                    await client.send_file('me', file_path, caption=cap)
                    os.remove(file_path)
                    saved_count += 1
                    logger.info("Media downloaded and sent successfully", message_id=message.id)
                else:
                    error_count += 1
                    last_error = "Media unsupported/WebPage"
                    logger.error("Download returned None (unsupported media)", message_id=message.id)
            except Exception as e:
                logger.error("Error saving media", error=str(e))
                last_error = str(e)
                error_count += 1
                
            # Update status berkala setiap 2 media agar tidak kena limit edit message
            if count % 2 == 0:
                try:
                    await status_msg.edit(
                        f"⏳ **Scraping in progress...**\n"
                        f"Media Ditemukan: `{count}/{limit}`\n"
                        f"Berhasil Disimpan: `{saved_count}`\n"
                        f"Gagal: `{error_count}`\n"
                        f"*(Jika gagal, bisa jadi karena media tidak didukung/webpage preview)*"
                    )
                except Exception:
                    pass # Ignore edit message errors
            
            # Random delay (2 - 5 detik) untuk mencegah ban / flood limit
            delay = random.uniform(2.0, 5.0)
            await asyncio.sleep(delay)
            
            if count >= limit:
                break
                
        err_text = f"\nError Terakhir: `{last_error}`" if last_error else ""
        await status_msg.edit(
            f"✅ **Scraping Selesai!**\n"
            f"Target: `{chat_id.id}`\n"
            f"Total Media Ditemukan: `{count}`\n"
            f"Berhasil Disimpan ke Saved Messages: `{saved_count}`\n"
            f"Gagal: `{error_count}`{err_text}"
        )
        logger.info("Scraping task completed", target=chat_id, saved=saved_count)
        
    except Exception as e:
        logger.error("Scrape task failed", error=str(e))
        try:
            await status_msg.edit(f"❌ **Scraping Gagal!**\nTerjadi kesalahan:\n`{str(e)}`")
        except:
            pass
