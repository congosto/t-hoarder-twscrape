Get-Process streamlit, python -ErrorAction SilentlyContinue | Stop-Process -Force
Set-Location "$PSScriptRoot\app"
streamlit run app.py
