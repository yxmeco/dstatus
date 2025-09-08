@echo off
git pull
git add --all
git commit -m "%date% %time%: Updated"
git push
@REM git push origin master
goto :eof


