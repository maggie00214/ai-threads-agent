"""
每日排程執行器
在本機每天早上 8:00 自動執行 agent.py

用法：python schedule_daily.py
（讓視窗保持開著，或設定為開機自動執行）
"""
import schedule
import time
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "agent.py"
RUN_TIME = "08:00"  # 24小時制，可自行修改


def run_agent():
    print(f"[排程] 開始執行 AI Agent...")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(SCRIPT.parent)
    )
    if result.returncode == 0:
        print("[排程] 執行完成")
    else:
        print(f"[排程] 執行失敗，exit code: {result.returncode}")


schedule.every().day.at(RUN_TIME).do(run_agent)

print(f"[排程] 已啟動，每天 {RUN_TIME} 自動執行")
print("[排程] 按 Ctrl+C 停止\n")

while True:
    schedule.run_pending()
    time.sleep(60)
