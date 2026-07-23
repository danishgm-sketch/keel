' Double-click once to put a "Keel" icon on your Desktop that launches the app
' with no console window. Windows only.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
repo = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = sh.SpecialFolders("Desktop")

Set lnk = sh.CreateShortcut(desktop & "\Keel.lnk")
lnk.TargetPath = "pythonw"
lnk.Arguments = "-m keel app --dir data"
lnk.WorkingDirectory = repo
lnk.Description = "Keel trading dashboard"
lnk.Save

MsgBox "Added 'Keel' to your Desktop. Double-click it to open the app.", 64, "Keel"
