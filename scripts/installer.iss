; Cavalry 87W installer. Built by scripts/build.py, which passes AppVersion, SourceDir, OutputDir and IconFile.

#define AppName "Cavalry 87W"
#define AppExe "Cavalry87.exe"

[Setup]
AppId={{6F3B2C1E-8A47-4D5B-9C2E-87C4A1D0F87A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Cavalry87
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user by default, no admin prompt; the first page offers installing for everyone instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=Cavalry87-Setup-v{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; A running copy is closed for the upgrade and started again afterwards.
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "autostart"; Description: "Start with Windows (in the tray)"; GroupDescription: "Startup:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Same value the app's own "Start with Windows" switch writes, so the switch shows it as on.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Cavalry87"; ValueData: """{app}\{#AppExe}"" --tray"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
; An update started from inside the app reopens it afterwards.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: Relaunch

[Code]
function RegisterWindowMessage(Name: String): Cardinal;
  external 'RegisterWindowMessageW@user32.dll stdcall';

// Ask a running copy to quit the normal way (it finishes any keyboard write first), then wait for it.
procedure QuitRunningApp();
var
  Tray: HWND;
  Waited: Integer;
begin
  Tray := FindWindowByWindowName('Cavalry87Tray');
  if Tray = 0 then
    exit;
  PostMessage(Tray, RegisterWindowMessage('Cavalry87.Quit'), 0, 0);
  Waited := 0;
  while (FindWindowByWindowName('Cavalry87Tray') <> 0) and (Waited < 15000) do
  begin
    Sleep(250);
    Waited := Waited + 250;
  end;
  Sleep(500);
end;

function Relaunch(): Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  QuitRunningApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  QuitRunningApp();
  Result := True;
end;

// The app can turn on starting with Windows by itself, so always clear that on uninstall.
// Profiles and backups in %APPDATA%\Cavalry87 are kept.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Cavalry87');
end;
