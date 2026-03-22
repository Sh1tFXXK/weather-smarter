@echo off
setlocal
set PYTHONPATH=E:\project\weather-smarter
echo PYTHONPATH=%PYTHONPATH%
E:\project\weather-smarter\.pyembed\python.exe -m pytest tests/test_decision_engine.py tests/test_decision_rules.py tests/test_nlp.py
