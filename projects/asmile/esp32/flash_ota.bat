@echo off
REM Flash ESP32 via WiFi (OTA) da Windows - nessun cavo USB.
REM Requisiti: arduino-cli + core esp32 + Python, stessa rete WiFi (SpadaBike).
REM Uso:  flash_ota.bat [IP]     (default: 192.168.1.134)

setlocal
set IP=%1
if "%IP%"=="" set IP=192.168.1.134
set OTA_PASS=otabike
set FQBN=esp32:esp32:esp32
set SKETCH=%~dp0esp32_wifi

echo >> compilo %SKETCH%
arduino-cli compile --fqbn %FQBN% "%SKETCH%"
if errorlevel 1 ( echo COMPILAZIONE FALLITA & exit /b 1 )

echo >> flash OTA su %IP%
arduino-cli upload -p %IP% --fqbn %FQBN% --upload-field password=%OTA_PASS% "%SKETCH%"
if errorlevel 1 ( echo FLASH FALLITO & exit /b 1 )

echo >> fatto. Apri nel browser:  http://%IP%/
endlocal
