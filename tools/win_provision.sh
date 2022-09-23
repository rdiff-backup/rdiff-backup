# provision Python for 32 and/or 64 bits in given version using Chocolatey

if [ "$1" == "asciidoc" ]
then
	choco install ruby
	gem install asciidoctor
	shift
fi

if [ "$1" == "python" ]
then
	PYTHON_VERSION=$2

	choco install python3 \
		--version ${PYTHON_VERSION} \
		--params "/InstallDir:C:\Python64 /InstallDir32:C:\Python32"
	shift 2
fi

function install_python_modules() {
	${PYEXE} -VV
	${PIPEXE} install --upgrade -r requs/base.txt -r requs/optional.txt \
		-r requs/build.txt -r requs/test.txt
	${PYEXE} -c 'import pywintypes, winnt, win32api, win32security, win32file, win32con'
}

if [ -n "$*" ]
then
	for bits in "${@}"
	do
		if [[ ${bits} == *64 ]]; then bits=64; else bits=32; fi
		PYEXE="C:/Python${bits}/python.exe"
		PIPEXE="C:/Python${bits}/Scripts/pip.exe"
		install_python_modules
	done
else
	PYEXE="python.exe"
	PIPEXE="pip.exe"
	install_python_modules
fi
