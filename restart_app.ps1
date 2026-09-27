Get-Process streamlit, python -ErrorAction SilentlyContinue | Stop-Process -Force
Set-Location "$PSScriptRoot\app"
python -m streamlit run app.py
