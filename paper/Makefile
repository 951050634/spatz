LATEXMK ?= latexmk
MAIN := main
BUILD_DIR := build

.PHONY: all pdf zh clean

all: pdf

pdf:
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error \
		-file-line-error -outdir=$(BUILD_DIR) $(MAIN).tex

zh:
	$(LATEXMK) -lualatex -interaction=nonstopmode -halt-on-error \
		-file-line-error -outdir=$(BUILD_DIR)/zh main-zh.tex
	cp $(BUILD_DIR)/zh/main-zh.pdf main-zh.pdf

clean:
	$(LATEXMK) -C -outdir=$(BUILD_DIR) $(MAIN).tex
