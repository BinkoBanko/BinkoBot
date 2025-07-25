#!/usr/bin/env python3
"""
Standalone script to run the Discord bot
"""
import asyncio
import os
import sys
from bot import main as bot_main

if __name__ == "__main__":
    print("Starting BinkoBot Discord Bot...")
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        print(f"Bot error: {e}")
        sys.exit(1)