PY ?= python3

.PHONY: all build sheet list clean test

all: build sheet

build:          ## render every content folder to out/
	$(PY) -m flyer build

sheet: build    ## build, then write the contact sheet at out/index.html
	$(PY) -m flyer sheet

list:           ## show the content folders and their photos
	$(PY) -m flyer list

test:
	$(PY) -m unittest discover -s tests -v

clean:
	rm -rf out
