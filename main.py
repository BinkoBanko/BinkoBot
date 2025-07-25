
import asyncio
import threading
import os
from app import app
from bot import main as bot_main

def run_flask():
    """Run the Flask web application"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def run_bot():
    """Run the Discord bot"""
    asyncio.run(bot_main())

if __name__ == "__main__":
    # Check if we should run bot, web app, or both
    run_mode = os.getenv("RUN_MODE", "both")  # both, bot, web
    
    if run_mode == "web":
        # Run only web app (current gunicorn setup)
        from app import app
    elif run_mode == "bot":
        # Run only bot
        asyncio.run(bot_main())
    else:
        # Run both (development mode)
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        # Run bot in main thread
        asyncio.run(bot_main())

# For gunicorn - start Discord bot in background when web app starts
import atexit

def start_bot_background():
    """Start Discord bot in background thread when imported by gunicorn"""
    if os.getenv("RUN_MODE", "both") in ["both", "bot"]:
        try:
            # Only start if we have a valid token
            token = os.getenv("DISCORD_BOT_TOKEN")
            if not token:
                print("❌ DISCORD_BOT_TOKEN not found - skipping bot startup")
                return
            
            # Validate token format (should be around 70 characters and contain dots)
            if len(token) < 50 or '.' not in token:
                print("❌ DISCORD_BOT_TOKEN appears invalid - skipping bot startup")
                return
            
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            print("✅ Discord bot started in background thread")
        except Exception as e:
            print(f"❌ Failed to start Discord bot: {e}")

# Only start bot automatically if not explicitly disabled and we're not in development
if os.getenv("DISABLE_AUTO_BOT") != "1" and __name__ != "__main__":
    start_bot_background()

# For gunicorn - export the Flask app
from app import app
