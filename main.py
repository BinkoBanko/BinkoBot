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
    # RUN_MODE: "both" (default), "bot", or "web"
    run_mode = os.getenv("RUN_MODE", "both")

    if run_mode == "web":
        run_flask()
    elif run_mode == "bot":
        run_bot()
    else:
        # Run both in one process: Flask in a background thread, bot in the
        # main thread. For a production deployment, prefer running the bot
        # and the web dashboard as two separate processes/services instead
        # (e.g. `python bot.py` + `gunicorn app:app`) so each can be
        # restarted and scaled independently.
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        run_bot()
