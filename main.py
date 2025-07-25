
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
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("Discord bot started in background thread")

# Start bot when imported by gunicorn
start_bot_background()

# For gunicorn - export the Flask app
from app import app
