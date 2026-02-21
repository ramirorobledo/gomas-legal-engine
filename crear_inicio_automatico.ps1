$WshShell = New-Object -comObject WScript.Shell
$startupPath = [System.Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startupPath "Gomas Legal Engine.lnk"
$Shortcut = $WshShell.CreateShortcut($lnkPath)
$Shortcut.TargetPath = "C:\Users\RAMIRO\Documents\GitHub\gomas-legal-engine\INICIAR.bat"
$Shortcut.WorkingDirectory = "C:\Users\RAMIRO\Documents\GitHub\gomas-legal-engine"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
Write-Host "Acceso directo creado en: $lnkPath"
