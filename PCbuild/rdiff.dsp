# Microsoft Developer Studio Project File - Name="rdiff" - Package Owner=<4>
# Microsoft Developer Studio Generated Build File, Format Version 6.00
# ** DO NOT EDIT **

# TARGTYPE "Win32 (x86) Application" 0x0101

CFG=rdiff - Win32 Debug
!MESSAGE This is not a valid makefile. To build this project using NMAKE,
!MESSAGE use the Export Makefile command and run
!MESSAGE 
!MESSAGE NMAKE /f "rdiff.mak".
!MESSAGE 
!MESSAGE You can specify a configuration when running NMAKE
!MESSAGE by defining the macro CFG on the command line. For example:
!MESSAGE 
!MESSAGE NMAKE /f "rdiff.mak" CFG="rdiff - Win32 Debug"
!MESSAGE 
!MESSAGE Possible choices for configuration are:
!MESSAGE 
!MESSAGE "rdiff - Win32 Release" (based on "Win32 (x86) Application")
!MESSAGE "rdiff - Win32 Debug" (based on "Win32 (x86) Application")
!MESSAGE 

# Begin Project
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
CPP=cl.exe
MTL=midl.exe
RSC=rc.exe

!IF  "$(CFG)" == "rdiff - Win32 Release"

# PROP BASE Use_MFC 0
# PROP BASE Use_Debug_Libraries 0
# PROP BASE Output_Dir "Release"
# PROP BASE Intermediate_Dir "Release"
# PROP BASE Target_Dir ""
# PROP Use_MFC 0
# PROP Use_Debug_Libraries 0
# PROP Output_Dir "Release"
# PROP Intermediate_Dir "Release"
# PROP Ignore_Export_Lib 0
# PROP Target_Dir ""
# ADD BASE CPP /nologo /W3 /GX /O2 /D "WIN32" /D "NDEBUG" /D "_WINDOWS" /D "_MBCS" /YX /FD /c
# ADD CPP /nologo /W3 /GX /O2 /I "." /I ".." /I "../popt" /D "NDEBUG" /D "WIN32" /D "_CONSOLE" /D "_MBCS" /YX /FD /c
# ADD BASE MTL /nologo /D "NDEBUG" /mktyplib203 /win32
# ADD MTL /nologo /D "NDEBUG" /mktyplib203 /win32
# ADD BASE RSC /l 0xc09 /d "NDEBUG"
# ADD RSC /l 0xc09 /d "NDEBUG"
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
LINK32=link.exe
# ADD BASE LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:windows /machine:I386
# ADD LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:console /machine:I386
# SUBTRACT LINK32 /pdb:none

!ELSEIF  "$(CFG)" == "rdiff - Win32 Debug"

# PROP BASE Use_MFC 0
# PROP BASE Use_Debug_Libraries 1
# PROP BASE Output_Dir "Debug"
# PROP BASE Intermediate_Dir "Debug"
# PROP BASE Target_Dir ""
# PROP Use_MFC 0
# PROP Use_Debug_Libraries 1
# PROP Output_Dir ".."
# PROP Intermediate_Dir "Debug"
# PROP Ignore_Export_Lib 0
# PROP Target_Dir ""
# ADD BASE CPP /nologo /W3 /Gm /GX /ZI /Od /D "WIN32" /D "_DEBUG" /D "_WINDOWS" /D "_MBCS" /YX /FD /GZ /c
# ADD CPP /nologo /W3 /Gm /GX /ZI /Od /I "." /I ".." /I "../popt" /D "_DEBUG" /D "WIN32" /D "_CONSOLE" /D "_MBCS" /YX /FD /GZ /c
# ADD BASE MTL /nologo /D "_DEBUG" /mktyplib203 /win32
# ADD MTL /nologo /D "_DEBUG" /mktyplib203 /win32
# ADD BASE RSC /l 0xc09 /d "_DEBUG"
# ADD RSC /l 0xc09 /d "_DEBUG"
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
LINK32=link.exe
# ADD BASE LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:windows /debug /machine:I386 /pdbtype:sept
# ADD LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:console /debug /machine:I386 /pdbtype:sept
# SUBTRACT LINK32 /pdb:none

!ENDIF 

# Begin Target

# Name "rdiff - Win32 Release"
# Name "rdiff - Win32 Debug"
# Begin Group "Source Files"

# PROP Default_Filter "cpp;c;cxx;rc;def;r;odl;idl;hpj;bat"
# Begin Source File

SOURCE=..\base64.c
# End Source File
# Begin Source File

SOURCE=..\buf.c
# End Source File
# Begin Source File

SOURCE=..\checksum.c
# End Source File
# Begin Source File

SOURCE=..\command.c
# End Source File
# Begin Source File

SOURCE=..\delta.c
# End Source File
# Begin Source File

SOURCE=..\emit.c
# End Source File
# Begin Source File

SOURCE=..\fileutil.c
# End Source File
# Begin Source File

SOURCE=..\popt\findme.c
# End Source File
# Begin Source File

SOURCE=..\hex.c
# End Source File
# Begin Source File

SOURCE=..\isprefix.c
# End Source File
# Begin Source File

SOURCE=..\job.c
# End Source File
# Begin Source File

SOURCE=..\mdfour.c
# End Source File
# Begin Source File

SOURCE=..\mksum.c
# End Source File
# Begin Source File

SOURCE=..\msg.c
# End Source File
# Begin Source File

SOURCE=..\netint.c
# End Source File
# Begin Source File

SOURCE=..\patch.c
# End Source File
# Begin Source File

SOURCE=..\popt\popt.c
# End Source File
# Begin Source File

SOURCE=..\popt\poptconfig.c
# End Source File
# Begin Source File

SOURCE=..\popt\popthelp.c
# End Source File
# Begin Source File

SOURCE=..\popt\poptparse.c
# End Source File
# Begin Source File

SOURCE=..\prototab.c
# End Source File
# Begin Source File

SOURCE=..\rdiff.c
# End Source File
# Begin Source File

SOURCE=..\readsums.c
# End Source File
# Begin Source File

SOURCE=..\scoop.c
# End Source File
# Begin Source File

SOURCE=..\search.c
# End Source File
# Begin Source File

SOURCE=..\snprintf.c
# End Source File
# Begin Source File

SOURCE=..\stats.c
# End Source File
# Begin Source File

SOURCE=..\stream.c
# End Source File
# Begin Source File

SOURCE=..\sumset.c
# End Source File
# Begin Source File

SOURCE=..\trace.c
# End Source File
# Begin Source File

SOURCE=..\tube.c
# End Source File
# Begin Source File

SOURCE=..\util.c
# End Source File
# Begin Source File

SOURCE=..\version.c
# End Source File
# Begin Source File

SOURCE=..\whole.c
# End Source File
# End Group
# Begin Group "Header Files"

# PROP Default_Filter "h;hpp;hxx;hm;inl"
# Begin Source File

SOURCE=..\acconfig.h
# End Source File
# Begin Source File

SOURCE=..\buf.h
# End Source File
# Begin Source File

SOURCE=..\checksum.h
# End Source File
# Begin Source File

SOURCE=..\command.h
# End Source File
# Begin Source File

SOURCE=.\config.h
# End Source File
# Begin Source File

SOURCE=..\emit.h
# End Source File
# Begin Source File

SOURCE=..\fileutil.h
# End Source File
# Begin Source File

SOURCE=..\popt\findme.h
# End Source File
# Begin Source File

SOURCE=..\isprefix.h
# End Source File
# Begin Source File

SOURCE=..\job.h
# End Source File
# Begin Source File

SOURCE=..\netint.h
# End Source File
# Begin Source File

SOURCE=..\popt\popt.h
# End Source File
# Begin Source File

SOURCE=..\popt\poptint.h
# End Source File
# Begin Source File

SOURCE=..\protocol.h
# End Source File
# Begin Source File

SOURCE=..\prototab.h
# End Source File
# Begin Source File

SOURCE=..\rsync.h
# End Source File
# Begin Source File

SOURCE=..\search.h
# End Source File
# Begin Source File

SOURCE=..\stream.h
# End Source File
# Begin Source File

SOURCE=..\sumset.h
# End Source File
# Begin Source File

SOURCE=..\popt\system.h
# End Source File
# Begin Source File

SOURCE=..\trace.h
# End Source File
# Begin Source File

SOURCE=..\types.h
# End Source File
# Begin Source File

SOURCE=..\util.h
# End Source File
# Begin Source File

SOURCE=..\whole.h
# End Source File
# End Group
# Begin Group "Resource Files"

# PROP Default_Filter "ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe"
# End Group
# End Target
# End Project
