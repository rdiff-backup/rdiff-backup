# provision Python for 32 and 64 bits in given version using Chocolatey

PYTHON_VERSION=$1

choco install python3 \
	--version ${PYTHON_VERSION} \
	--params "/InstallDir:C:\Python64 /InstallDir32:C:\Python32"

for bits in 32 64
do
	C:/Python${bits}/python.exe -VV
	C:/Python${bits}/Scripts/pip.exe install --upgrade \
		pywin32 pyinstaller==5.1 wheel certifi setuptools-scm tox PyYAML
# FIXME PyInstaller 5.2 and 5.3 fail to grab all modules
	C:/Python${bits}/python.exe -c \
		'import pywintypes, winnt, win32api, win32security, win32file, win32con'
done
