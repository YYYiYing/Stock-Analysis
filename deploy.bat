@echo off
chcp 65001 >nul
REM YYIH 手動部署 - 確認OK後點擊
cd /d "%~dp0"
echo === YYIH Deploy ===
echo [1/3] 清理殘留 worktree（避免卡在 logs 刪除）...
git worktree prune 2>nul
if exist ".git\worktrees" (
  for /d %%W in (.git\worktrees\*) do (
    rmdir /s /q "%%W" 2>nul
  )
)
git status --porcelain
set /p MSG="請輸入說明 (Enter預設): "
if "%MSG%"=="" set MSG=manual deploy %date% %time%
echo [2/3] 提交...
git add reports/ scripts/
git commit -m "%MSG%" 2>nul
if errorlevel 1 echo 無變更或提交略過
echo [3/3] 推送...
git push origin main
if errorlevel 1 (
  echo 推送失敗，請檢查網路或權限
) else (
  echo 部署完成，已推送至 origin/main
)
pause
