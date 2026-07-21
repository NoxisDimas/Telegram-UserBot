import asyncio
import os
from telethon import TelegramClient
from app.config import config
from app.utils.logger import setup_logger, get_logger

async def main():
    # Setup logging agar kita bisa melihat prosesnya
    setup_logger()
    logger = get_logger("SessionGenerator")
    
    print("="*50)
    print("TELEGRAM SESSION GENERATOR (Master-Worker)")
    print("="*50)
    print("Script ini akan membantu Anda login secara interaktif.")
    print("Pastikan .env sudah terisi dengan API_ID dan API_HASH.")
    print(f"Untuk Owner, ketik: {config.OWNER_SESSION_NAME}")
    print("Untuk Worker, ketik bebas (misal: worker1, worker2)")
    print("-"*50)

    try:
        # Validate config before starting
        config.validate()
        
        session_name = input("Ketik nama sesi: ").strip()
        if not session_name:
            print("❌ Nama sesi tidak boleh kosong!")
            return
            
        os.makedirs(config.SESSION_PATH, exist_ok=True)
        session_file_path = os.path.join(config.SESSION_PATH, session_name)
        
        client = TelegramClient(
            session_file_path,
            config.TG_API_ID,
            config.TG_API_HASH
        )
        
        # client.start() pada Telethon akan otomatis meminta:
        # 1. Nomor HP
        # 2. Kode OTP (dikirim via Telegram/SMS)
        # 3. Password 2FA (jika aktif)
        await client.start()
        
        me = await client.get_me()
        
        print("-"*50)
        print(f"✅ Login Berhasil untuk sesi: {session_name}")
        print(f"👤 Nama: {me.first_name}")
        print(f"🆔 ID: {me.id}")
        print(f"📂 File session disimpan di folder '{config.SESSION_PATH}/{session_name}.session'")
        print("-"*50)
        
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
    finally:
        if 'client' in locals() and client:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
