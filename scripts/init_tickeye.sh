#!/bin/bash

mkdir -p {monitor,config,utils}

touch main.py
touch requirements.txt

touch monitor/__init__.py
touch monitor/fetcher.py
touch monitor/rules.py
touch monitor/notifier.py

touch utils/logger.py
touch config/settings.yaml

echo "✅ TickEye 项目结构已成功创建。"
