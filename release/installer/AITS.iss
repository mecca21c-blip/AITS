#define MyAppName "AITS"
#define MyAppVersion "1.0.0-rc.1"
#ifndef ReleaseDir
  #define ReleaseDir "..\output\release_candidate\AITS"
#endif

[Setup]
AppId={{A9057B9A-6B05-4DAA-8D4C-2DF3C52B7431}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\AITS
DefaultGroupName=AITS
OutputDir=..\output\release_candidate
OutputBaseFilename=AITS-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
Uninstallable=yes
DisableProgramGroupPage=yes

[Files]
Source: "{#ReleaseDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AITS"; Filename: "{app}\AITS.exe"
Name: "{autodesktop}\AITS"; Filename: "{app}\AITS.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 바로가기 만들기"; Flags: unchecked

[Messages]
WelcomeLabel2=AITS는 Python 또는 Ollama 설치 없이 동작합니다.%n%n최초 실행은 OFF 상태이며 사용자 데이터는 LocalAppData에 보존됩니다.

[UninstallDelete]
; User data under LocalAppData is intentionally preserved.
