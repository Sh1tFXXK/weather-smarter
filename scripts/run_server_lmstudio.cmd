@echo off
setlocal
cd /d %~dp0..

set LLM_PROVIDER=openai
set OPENAI_BASE_URL=http://127.0.0.1:1234/v1
set OPENAI_COMPAT_MODE=chat
set OPENAI_API_KEY=lm-studio
set LLM_MODEL=qwen3-0.6b
set LLM_RESPONSE_FORMAT=text

".\.pyembed\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
