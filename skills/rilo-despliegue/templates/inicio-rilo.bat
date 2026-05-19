@echo off
REM inicio-rilo.bat — Auto-arranque del sistema RILO SAS para Sandra
REM Colocar en shell:startup (Win+R, pegar "shell:startup")

wsl -e bash -c "cd ~/rilo-dashboard && npm run dev & cd ~/rilo-backend && source venv/bin/activate && python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000"
