' Launch Life Manager with no console window.
' Runs desktop_app.py via pythonw from the project directory.
Option Explicit

Dim shell, fso, here, pyw, target

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Project directory = folder this script lives in.
here = fso.GetParentFolderName(WScript.ScriptFullName)

' Prefer pythonw so no console flashes; fall back to python.
pyw = "pythonw"

target = Chr(34) & pyw & Chr(34) & " " & _
         Chr(34) & fso.BuildPath(here, "desktop_app.py") & Chr(34)

' Make relative paths inside the app resolve correctly.
shell.CurrentDirectory = here

' 0 = hidden window, False = don't wait for it to finish.
shell.Run target, 0, False
