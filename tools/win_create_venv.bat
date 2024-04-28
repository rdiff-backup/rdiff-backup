@ECHO ON
@REM create a Python virtualenv to test rdiff-backup
IF "%1" EQU "" (
	mkdir dist
	SET venv_dir=dist/rdb
) ELSE (
	mkdir %~dp1
	SET venv_dir=%1
)
python -m venv %venv_dir%
timeout /t 1 /NOBREAK
python -m venv --upgrade --upgrade-deps %venv_dir%
CALL %venv_dir%\Scripts\activate
pip install -r requirements.txt
@REM this last command installs the currently developed version, repeat as needed!
pip install .
deactivate
