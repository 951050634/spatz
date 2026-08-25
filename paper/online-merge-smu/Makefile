PAPER := main
PYTHON ?= python3

.PHONY: all clean check figures

all: $(PAPER).pdf

figures:
	$(PYTHON) ../../experiments/scripts/make_paper_architecture_figures.py

$(PAPER).pdf: $(PAPER).tex refs.bib figures

	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

check: $(PAPER).pdf

	pdfinfo $(PAPER).pdf | grep Pages
	grep -n "LaTeX Warning.*undefined" $(PAPER).log || true
	pdffonts $(PAPER).pdf | awk 'NR > 2 && $$(NF-4) != "yes" {print}'

clean:
	latexmk -C
