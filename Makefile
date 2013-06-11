.PHONY: clean prepare docs

prepare: clean
	tools/fixver.sh

docs:
	python3 -c 'import sys, sphinx; sys.exit(sphinx.main(sys.argv))' -b html -d build/doctrees docs build/html

clean:
	-rm -rf build/ dist/ MANIFEST 2>/dev/null
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '._*' -exec rm -f {} +
	find . -name '.coverage*' -exec rm -f {} +

