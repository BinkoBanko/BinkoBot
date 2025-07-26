#!/usr/bin/env python3
"""
Full system runner - starts both Discord bot and web application
"""
import asyncio
import threading
import time
import os
import sys

def run_web_app():
    """Run the Flask web application"""
    from main import app
    app.run(host='0.0.0.0', port=5000, debug=False)

async def run_discord_bot():
    """Run the Discord bot"""
    from bot import main
    await main()

def main():
    print("🚀 Starting BinkoBot Full System...")
    
    # Start web app in a separate thread
    web_thread = threading.Thread(target=run_web_app, daemon=True)
    web_thread.start()
    print("✅ Web application started on port 5000")
    
    # Give web app time to start
    time.sleep(2)
    
    # Start Discord bot in main thread
    print("✅ Starting Discord bot...")
    try:
        asyncio.run(run_discord_bot())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Discord bot error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
