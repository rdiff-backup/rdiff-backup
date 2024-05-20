@ECHO OFF
REM batch script to backup using rdiff-backup:
REM from the current user's home directory
REM to a repository within the script's directory
REM The file <script>.txt in the same directory is used to include/exclude files
REM Just start this batch script to start the back-up
REM and do NOT eject and remove the drive before it is finished!

SET RDIFFSRCDIR=%USERPROFILE%
SET RDIFFTGTDIR=%~dp0BAK__%COMPUTERNAME%__%USERNAME%
SET RDIFFEXE=%~dp0rdiff-backup\rdiff-backup.exe
SET RDIFFGLOBS=%~dpn0.txt

ECHO == Backing up %RDIFFSRCDIR% to %RDIFFTGTDIR% using %RDIFFEXE% filtered by %RDIFFGLOBS% ==

%RDIFFEXE% --version

%RDIFFEXE% -v5 --api-version 201 backup --include-globbing-filelist %RDIFFGLOBS% %RDIFFSRCDIR% %RDIFFTGTDIR%

%RDIFFEXE% list increments %RDIFFTGTDIR%

fsutil volume diskfree %RDIFFTGTDIR%

SET /p wait_variable=Check above results and hit ENTER to continue...
