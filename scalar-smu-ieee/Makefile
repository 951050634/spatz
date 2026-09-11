LATEXMK ?= latexmk
MAIN := main
BUILD_DIR := build

.PHONY: all pdf clean

all: pdf

pdf:
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error \
		-file-line-error -outdir=$(BUILD_DIR) $(MAIN).tex

clean:
	$(LATEXMK) -C -outdir=$(BUILD_DIR) $(MAIN).tex
