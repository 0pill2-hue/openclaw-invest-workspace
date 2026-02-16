import asyncio
import os
import qrcode
from telethon import TelegramClient
from datetime import datetime, timedelta, timezone

api_id = 35868757
api_hash = 'deafd5814a10ccbe7b516586a60f04ed'
session_name = 'jobis_mtproto_session'
qr_path = '/Users/jobiseu/.openclaw/workspace/invest/tg_qr.png'
status_file = '/Users/jobiseu/.openclaw/workspace/invest/tg_status.txt'

async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()
    
    if await client.is_user_authorized():
        print("ALREADY_AUTHORIZED")
        with open(status_file, 'w') as f: f.write("AUTHORIZED")
    else:
        print("Starting QR login flow...")
        qr_login = await client.qr_login()
        
        # Generate QR Image
        qr_url = qr_login.url
        img = qrcode.make(qr_url)
        img.save(qr_path)
        
        with open(status_file, 'w') as f: f.write("QR_READY")
        print(f"QR code saved to {qr_path}. Waiting for scan...")
        
        try:
            # Wait for scan with timeout
            user = await qr_login.wait(timeout=300)
            print(f"Login success: {user.first_name}")
            with open(status_file, 'w') as f: f.write("AUTHORIZED")
            if os.path.exists(qr_path): os.remove(qr_path)
        except Exception as e:
            print(f"Login failed or timed out: {e}")
            with open(status_file, 'w') as f: f.write(f"FAILED: {e}")
            if os.path.exists(qr_path): os.remove(qr_path)

if __name__ == '__main__':
    # Force output to be seen immediately
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(main())
