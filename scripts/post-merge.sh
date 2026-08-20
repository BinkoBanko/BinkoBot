#!/bin/bash
set -e

# Install / sync all Python dependencies from requirements.txt.
# Runs after every task merge to keep the environment up to date.
pip install -q -r requirements.txt
# Install dev/test tools not in requirements.txt
pip install -q pytest pytest-asyncio
