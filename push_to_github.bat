@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在推送至 https://github.com/RuleLight/instruments_tunner.git ...
git remote set-url origin "https://github.com/RuleLight/instruments_tunner.git" 2>nul || git remote add origin "https://github.com/RuleLight/instruments_tunner.git"
git push -u origin main
echo.
echo ✅ 已成功开源并推送至 https://github.com/RuleLight/instruments_tunner
pause
