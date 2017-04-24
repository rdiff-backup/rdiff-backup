"""Last tested, this was *not* operational, but was only used as a guide to
re-establish a working Win32 build. This was initially copied from
https://lists.nongnu.org/archive/html/rdiff-backup-users/2009-02/msg00110.html
from the post by Josh Nisly."""
import glob
import os
import shutil
import sys
import tarfile
import urllib

RDIFF_BACKUP_VERSION = '1.2.2'
RDIFF_BACKUP_NAME = 'rdiff-backup-'+RDIFF_BACKUP_VERSION

RDIFF_BACKUP_URL = 'http://savannah.nongnu.org/download/rdiff-backup/'+RDIFF_BACKUP_NAME+'.tar.gz'
LIBRSYNC_URL = 'http://superb-east.dl.sourceforge.net/sourceforge/librsync/librsync-0.9.7.tar.gz'


LIBRSYNC_VCPROJ_TEXT = r"""<?xml version="1.0" encoding="Windows-1252"?>
<VisualStudioProject
        ProjectType="Visual C++"
        Version="9.00"
        Name="librsync"
        ProjectGUID="{B7D1448D-017B-4035-86A1-12B5B736101F}"
        RootNamespace="librsync"
        Keyword="Win32Proj"
        TargetFrameworkVersion="131072"
        >
        <Platforms>
                <Platform
                        Name="Win32"
                />
        </Platforms>
        <ToolFiles>
        </ToolFiles>
        <Configurations>
                <Configuration
                        Name="Release|Win32"
                        OutputDirectory="Release"
                        IntermediateDirectory="Release"
                        ConfigurationType="4"

InheritedPropertySheets="$(VCInstallDir)VCProjectDefaults\UpgradeFromVC71.vsprops"
                        CharacterSet="2"
                        >
                        <Tool
                                Name="VCPreBuildEventTool"
                        />
                        <Tool
                                Name="VCCustomBuildTool"
                        />
                        <Tool
                                Name="VCXMLDataGeneratorTool"
                        />
                        <Tool
                                Name="VCWebServiceProxyGeneratorTool"
                        />
                        <Tool
                                Name="VCMIDLTool"
                        />
                        <Tool
                                Name="VCCLCompilerTool"
                                AdditionalIncludeDirectories="popt; .\"

PreprocessorDefinitions="WIN32;NDEBUG;_LIB;HAVE_STRERROR"
                                MinimalRebuild="true"
                                RuntimeLibrary="0"
                                UsePrecompiledHeader="0"
                                WarningLevel="3"
                                Detect64BitPortabilityProblems="false"
                                DebugInformationFormat="3"
                        />
                        <Tool
                                Name="VCManagedResourceCompilerTool"
                        />
                        <Tool
                                Name="VCResourceCompilerTool"
                        />
                        <Tool
                                Name="VCPreLinkEventTool"
                        />
                        <Tool
                                Name="VCLibrarianTool"
                                OutputFile="$(OutDir)/rsync.lib"
                                IgnoreAllDefaultLibraries="true"
                                IgnoreDefaultLibraryNames=""
                        />
                        <Tool
                                Name="VCALinkTool"
                        />
                        <Tool
                                Name="VCXDCMakeTool"
                        />
                        <Tool
                                Name="VCBscMakeTool"
                        />
                        <Tool
                                Name="VCFxCopTool"
                        />
                        <Tool
                                Name="VCPostBuildEventTool"
                        />
                </Configuration>
        </Configurations>
        <References>
        </References>
        <Files>
                <Filter
                        Name="Source Files"
                        Filter="cpp;c;cxx;def;odl;idl;hpj;bat;asm;asmx"

UniqueIdentifier="{4FC737F1-C7A5-4376-A066-2A32D752A2FF}"
                        >
                        <File
                                RelativePath=".\base64.c"
                                >
                        </File>
                        <File
                                RelativePath=".\buf.c"
                                >
                        </File>
                        <File
                                RelativePath=".\checksum.c"
                                >
                        </File>
                        <File
                                RelativePath=".\command.c"
                                >
                        </File>
                        <File
                                RelativePath=".\delta.c"
                                >
                        </File>
                        <File
                                RelativePath=".\emit.c"
                                >
                        </File>
                        <File
                                RelativePath=".\fileutil.c"
                                >
                        </File>
                        <File
                                RelativePath=".\popt\findme.c"
                                >
                        </File>
                        <File
                                RelativePath=".\hex.c"
                                >
                        </File>
                        <File
                                RelativePath=".\isprefix.c"
                                >
                        </File>
                        <File
                                RelativePath=".\job.c"
                                >
                        </File>
                        <File
                                RelativePath=".\mdfour.c"
                                >
                        </File>
                        <File
                                RelativePath=".\mksum.c"
                                >
                        </File>
                        <File
                                RelativePath=".\msg.c"
                                >
                        </File>
                        <File
                                RelativePath=".\netint.c"
                                >
                        </File>
                        <File
                                RelativePath=".\patch.c"
                                >
                        </File>
                        <File
                                RelativePath=".\popt\popt.c"
                                >
                        </File>
                        <File
                                RelativePath=".\popt\poptconfig.c"
                                >
                        </File>
                        <File
                                RelativePath=".\popt\popthelp.c"
                                >
                        </File>
                        <File
                                RelativePath=".\popt\poptparse.c"
                                >
                        </File>
                        <File
                                RelativePath=".\prototab.c"
                                >
                        </File>
                        <File
                                RelativePath=".\rdiff.c"
                                >
                        </File>
                        <File
                                RelativePath=".\readsums.c"
                                >
                        </File>
                        <File
                                RelativePath=".\rollsum.c"
                                >
                        </File>
                        <File
                                RelativePath=".\scoop.c"
                                >
                        </File>
                        <File
                                RelativePath=".\search.c"
                                >
                        </File>
                        <File
                                RelativePath=".\snprintf.c"
                                >
                        </File>
                        <File
                                RelativePath=".\stats.c"
                                >
                        </File>
                        <File
                                RelativePath=".\stream.c"
                                >
                        </File>
                        <File
                                RelativePath=".\sumset.c"
                                >
                        </File>
                        <File
                                RelativePath=".\trace.c"
                                >
                        </File>
                        <File
                                RelativePath=".\tube.c"
                                >
                        </File>
                        <File
                                RelativePath=".\util.c"
                                >
                        </File>
                        <File
                                RelativePath=".\version.c"
                                >
                        </File>
                        <File
                                RelativePath=".\whole.c"
                                >
                        </File>
                </Filter>
        </Files>
        <Globals>
        </Globals>
</VisualStudioProject>
"""

LIBRSYNC_SLN_TEXT = r"""Microsoft Visual Studio Solution File, Format Version
10.00
# Visual C++ Express 2008
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "librsync",
"librsync.vcproj", "{B7D1448D-017B-4035-86A1-12B5B736101F}"
EndProject
Global
        GlobalSection(SolutionConfigurationPlatforms) = preSolution
                Debug|Win32 = Debug|Win32
                Release|Win32 = Release|Win32
        EndGlobalSection
        GlobalSection(ProjectConfigurationPlatforms) = postSolution
                {B7D1448D-017B-4035-86A1-12B5B736101F}.Debug|Win32.ActiveCfg =
Debug|Win32
                {B7D1448D-017B-4035-86A1-12B5B736101F}.Debug|Win32.Build.0 =
Debug|Win32
                {B7D1448D-017B-4035-86A1-12B5B736101F}.Release|Win32.ActiveCfg
= Release|Win32
                {B7D1448D-017B-4035-86A1-12B5B736101F}.Release|Win32.Build.0 =
Release|Win32
        EndGlobalSection
        GlobalSection(SolutionProperties) = preSolution
                HideSolutionNode = FALSE
        EndGlobalSection
EndGlobal
"""

LIBRSYNC_PATCH_TEXT="""diff -w -Nur librsync-0.9.7/buf.c librsync-0.9.7dev/buf.c
--- librsync-0.9.7/buf.c        2004-02-07 18:17:57.000000000 -0500
+++ librsync-0.9.7-win/buf.c    2008-11-20 12:28:23.000000000 -0500
@@ -59,6 +59,11 @@
 #define fseek fseeko
 #endif

+#ifdef NEED_FSEEKI64
+int __cdecl _fseeki64(FILE *, __int64, int);
+#define fseek _fseeki64
+#endif
+
 /**
  * File IO buffer sizes.
  */
diff -urN librsync-0.9.7/mdfour.h librsync-0.9.7dev/mdfour.h
--- librsync-0.9.7/mdfour.h     2004-02-07 18:17:57.000000000 -0500
+++ librsync-0.9.7dev/mdfour.h  2006-03-06 03:21:46.000000000 -0500
@@ -24,7 +24,7 @@
 #include "types.h"

 struct rs_mdfour {
-    int                 A, B, C, D;
+    unsigned int        A, B, C, D;
 #if HAVE_UINT64
     uint64_t            totalN;
 #else
diff -urN librsync-0.9.7/patch.c librsync-0.9.7dev/patch.c
--- librsync-0.9.7/patch.c      2004-09-17 17:35:50.000000000 -0400
+++ librsync-0.9.7dev/patch.c   2006-03-06 03:21:06.000000000 -0500
@@ -214,12 +214,12 @@
     void            *buf, *ptr;
     rs_buffers_t    *buffs = job->stream;

-    len = job->basis_len;
-
     /* copy only as much as will fit in the output buffer, so that we
      * don't have to block or store the input. */
-    if (len > buffs->avail_out)
+    if (job->basis_len > buffs->avail_out)
         len = buffs->avail_out;
+    else
+        len = job->basis_len;

     if (!len)
         return RS_BLOCKED;
"""

CONFIG_H_TEXT = """
#define SIZEOF_UNSIGNED_INT 4

#define PACKAGE "librsync"
#define VERSION "0.9.7"
#define RS_CANONICAL_HOST "librsync.sourceforge.net"

#define inline
#define NEED_FSEEKI64
"""


class BuildError(Exception):
        pass

def copy(src_pattern, dest_dir):
        if '*' in src_pattern:
                files = glob.glob(src_pattern)
        else:
                files = [src_pattern]
        for file in files:
                shutil.copyfile(file, os.path.join(dest_dir,
os.path.basename(file)))

def unzip(src_file, target_dir):
        print 'Extracting %s...' % src_file
        extension = src_file.rpartition('.')[2]
        tar = tarfile.open(src_file, 'r:'+extension)
        for tarinfo in tar:
                dest_path = os.path.join(target_dir, tarinfo.name.replace('/',
os.sep))
                if tarinfo.isreg():
                        tar.extract(tarinfo, target_dir)
                elif tarinfo.isdir():
                        if not os.path.isdir(dest_path):
                                os.mkdir(dest_path)
                elif tarinfo.issym():
                        pass # We don't care about symlinks
                else:
                        raise ValueError, 'Unhandled .tar.gz file:'+str(tarinfo)
        tar.close()

def verify_env(require_cvs):
        for path in os.environ['PATH'].split(';'):
                if os.path.exists(os.path.join(path, 'MSBuild.exe')):
                        break
        else:
                raise BuildError, '''This script must be run from \
the Visual Studio 2008 Commandline.'''

        if require_cvs:
                for path in os.environ['PATH'].split(';'):
                        if os.path.exists(os.path.join(path, 'cvs.exe')):
                                break
                else:
                        raise BuildError, '''Cvs.exe (CVSNT) must be in the
path.'''

def download_file(url, target_dir):
        filename = os.path.basename(url)
        target_name = os.path.join(target_dir, filename)
        if not os.path.exists(target_name):
                print 'Downloading %s...' % url
                urllib.urlretrieve(url, target_name)

        unzip(target_name, target_dir)

def write_text(filepath, text):
        file = open(filepath, 'w')
        file.write(text)
        file.close()

def build_librsync(root_dir):
        # Download package if necessary
        download_file(LIBRSYNC_URL, root_dir)

        # Add in support files
        librsync_dir = os.path.join(root_dir, 'librsync-0.9.7')
        write_text(os.path.join(librsync_dir, 'librsync.sln'),
LIBRSYNC_SLN_TEXT)
        write_text(os.path.join(librsync_dir, 'librsync.vcproj'),
LIBRSYNC_VCPROJ_TEXT)
        write_text(os.path.join(librsync_dir, 'config.h'), CONFIG_H_TEXT)

        # Patch for 4GB support
        large_file_patch = os.path.join(librsync_dir, 'lfs_support.patch')
        write_text(large_file_patch, LIBRSYNC_PATCH_TEXT)
        os.chdir(root_dir)
        if os.system('patch.exe -p0 < %s' % large_file_patch):
                raise BuildError, 'Unable to patch librsync.'

        # Build
        sln_path = os.path.join(librsync_dir, 'librsync.sln')
        if os.system('MSBuild.exe %s /t:Build /p:Configuration=Release' %
sln_path):
                raise BuildError, 'Unable to build librsync.'

        # Copy built library to where rdiff-backup's setup.py expects it
        output_dir = os.path.join(librsync_dir, 'lib')
        if not os.path.isdir(output_dir):
                os.mkdir(output_dir)
        lib_path = os.path.join(librsync_dir, 'Release', 'rsync.lib')
        copy(lib_path, output_dir)

        # Copy include files to where rdiff-backup expects them
        include_dir = os.path.join(librsync_dir, 'include')
        if not os.path.isdir(include_dir):
                os.mkdir(include_dir)
        for file in ('librsync.h', 'librsync-config.h'):
                copy(os.path.join(librsync_dir, file), include_dir)

def build_rdiff_backup(use_cvs, rebuild, root_dir, output_dir):
        rdiff_dir = os.path.join(root_dir, 'rdiff-backup')
        librsync_dir = os.path.join(root_dir, 'librsync-0.9.7')

        # Check out rdiff-backup
        if rebuild:
                if os.path.exists(rdiff_dir):
                        shutil.rmtree(rdiff_dir)

        if use_cvs:
                if not os.path.isdir(rdiff_dir):
                        os.chdir(root_dir)
                        if os.system('cvs -z3 -d:pserver:address@hidden:/sources/rdiff-backup co .'):
                                raise BuildError, 'Unable to check out rdiff-backup!'

                        # Patch rdiff-backup
                        os.chdir(rdiff_dir)
                        patch_exe = 'patch.exe'
                        for patch in ('rdiff-backup-windows-drive.patch',):
                                patch_path = os.path.join(root_dir, '..', patch)
                                print 'patching:', patch
                                if os.system('%s -N -p0 < %s' % (patch_exe, patch_path)):
                                        raise BuildError, 'Unable to patch rdiff-backup!'

                # Make an rdiff-backup dist package
                os.chdir(rdiff_dir)
                if os.system('python dist\\makedist ' + RDIFF_BACKUP_VERSION):
                        raise BuildError, 'Unable to make rdiff-backup dist package.'

                # There is now a built version in the rdiff-backup dir.
                # Extract it, build it, and copy the exe to output_dir.
                rdiff_output_name = 'rdiff-backup-'+RDIFF_BACKUP_VERSION
                target_dir = os.path.join(rdiff_dir, rdiff_output_name)
                if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                rdiff_tar = target_dir + '.tar.gz'
                unzip(rdiff_tar, rdiff_dir)
        else:
                if not os.path.exists(rdiff_dir):
                        os.mkdir(rdiff_dir)
                download_file(RDIFF_BACKUP_URL, rdiff_dir)
                rdiff_output_name = RDIFF_BACKUP_NAME

        rdiff_output_dir = os.path.join(rdiff_dir, rdiff_output_name)
        os.chdir(rdiff_output_dir)

        # Build rdiff-backup
        if os.system('setup.py build --librsync-dir=%s --lflags=%s' % \
                        (librsync_dir, '"/NODEFAULTLIB:libcmt.lib msvcrt.lib"')):
                raise BuildError, 'Unable to build rdiff-backup.'
        if os.system('setup.py py2exe --single-file > NUL'):
                raise BuildError, 'Unable to rdiff-backup via py2exe.'

        copy(os.path.join(rdiff_output_dir, 'dist', 'rdiff-backup.exe'), output_dir)

if __name__ == '__main__':
        root_dir = os.path.dirname(__file__)
        target_dir = os.path.join(root_dir, 'temp')
        output_dir = os.path.join(root_dir, 'output')
        rebuild = '--rebuild' in sys.argv[1:]
        use_cvs = '--cvs' in sys.argv[1:]
        for dir in (target_dir, output_dir):
                if not os.path.isdir(dir):
                        os.makedirs(dir)

        verify_env(use_cvs)
        build_librsync(target_dir)
        build_rdiff_backup(use_cvs, rebuild, target_dir, output_dir)
