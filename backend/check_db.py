#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import sqlite3

# 设置输出编码
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('agent.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("Database tables:")
for t in tables:
    print(f"  - {t[0]}")

# 检查 task_queue 表
print("\nChecking task_queue table:")
try:
    cursor.execute("PRAGMA table_info(task_queue)")
    cols = cursor.fetchall()
    if cols:
        print("task_queue table structure:")
        for c in cols:
            print(f"  {c[1]} ({c[2]})")
    else:
        print("  task_queue table does NOT exist")
except Exception as e:
    print(f"  Error: {e}")

conn.close()
