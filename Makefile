PY ?= python3
WEB_DPI ?= 150

.PHONY: all build sheet web list clean test

all: build sheet

build:          ## render every content folder to out/
	$(PY) -m flyer build

sheet: build    ## build, then write the contact sheet at out/index.html
	$(PY) -m flyer sheet

web:            ## rescreen at $(WEB_DPI) dpi and build lighter SVGs to out/web
	rm -rf build/web
	mkdir -p build/web
	cp -R content build/web/content
	$(PY) tools/halftone.py --content build/web/content --dpi $(WEB_DPI) --write
	$(PY) -m flyer --content build/web/content build --out out/web
	$(PY) -m flyer --content build/web/content sheet --out out/web

list:           ## show the content folders and their photos
	$(PY) -m flyer list

test:
	$(PY) -m unittest discover -s tests -v

clean:
	rm -rf out build
