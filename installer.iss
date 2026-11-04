#define AppName "MoM Toolbox"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "MoM_Toolbox.exe"

[Setup]
AppId={{8C1E2A64-5B0E-4E7A-9C51-3F1D2B7A9E10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Rajaguru Irusan
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=MoM_Toolbox_Setup_v{#AppVersion}
SetupIconFile=mom.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\MoM_Toolbox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
