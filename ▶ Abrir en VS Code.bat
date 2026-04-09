@echo off
echo Abriendo RestaurantOS en VS Code...
code "C:\Users\noahc\Documents\Claude\Projects\APP RESTAURANTE"
echo.
echo Iniciando Streamlit...
timeout /t 3 /nobreak >nul
cd /d "C:\Users\noahc\Documents\Claude\Projects\APP RESTAURANTE"
streamlit run app.py
pause
