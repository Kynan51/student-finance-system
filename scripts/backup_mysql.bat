@echo off
REM Back up the MySQL database on Windows. Requires mysqldump on PATH
REM (installed with MySQL Server / MySQL Workbench). Edit the values below.
set DB_NAME=student_finance
set DB_USER=student_finance_user
set DB_HOST=127.0.0.1
set DB_PORT=3306
cd /d "%~dp0\.."
if not exist backups mkdir backups
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set STAMP=%%i
mysqldump --single-transaction --no-tablespaces -h %DB_HOST% -P %DB_PORT% -u %DB_USER% -p %DB_NAME% > backups\%DB_NAME%_%STAMP%.sql
echo Backup written to backups\%DB_NAME%_%STAMP%.sql
pause
