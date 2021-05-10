@ECHO OFF
REM simple wrapper script to call rdiff-backup from the repo
REM d=Disk, p=(dir)path, n=name(without extension), x=extension
python "%~dpn0" %*
