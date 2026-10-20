Get-Process streamlit, python -ErrorAction SilentlyContinue | Stop-Process -Force
Set-Location "$PSScriptRoot"
python -m streamlit run app/app.py
