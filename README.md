
# book-converter

A command-line tool for restoring the text of scanned books. It runs OCR on a scanned PDF, uses a local LLM to fix OCR errors (broken words, hyphenation, stray characters, unwanted line breaks) while preserving structure, and exports the corrected result as both a PDF and an EPUB.

## How it works

1. **OCR / layout extraction** — [PaddleOCR (PP-StructureV3)](https://github.com/PaddlePaddle/PaddleOCR) reads the input PDF (configured for Spanish, `lang="es"`) and converts each page to Markdown, including detected images.
2. **Text restoration** — The page Markdown is split into overlapping chunks and sent to a local instance of **Qwen2.5-3B-Instruct**, run through `llama-cpp-python`. A system prompt instructs the model to fix hyphenation, rejoin broken paragraphs, and correct OCR character errors, without summarizing or adding content.
3. **Export** — The corrected Markdown is converted to HTML and then written out as:
   - a `.pdf` file (via `xhtml2pdf`)
   - a `.epub` file (via `EbookLib`), with detected images embedded

## Requirements

- **Python 3.12.10**
- The packages listed in `requirements.txt` (install with the command below)
- Enough RAM/VRAM to run a 3B-parameter GGUF model locally. A GPU is optional but recommended (`n_gpu_layers=-1` in the script offloads all layers to GPU if available; it will fall back to CPU otherwise)
- Internet access on first run, since `Llama.from_pretrained(...)` downloads the `Qwen/Qwen2.5-3B-Instruct-GGUF` model from Hugging Face the first time it's used (it's cached locally afterward)

### Installation

```bash
# (recommended) create a virtual environment
python3.12 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt
```

> Note: `paddlepaddle`, `paddleocr`, and `llama-cpp-python` can be heavy to install and may need platform-specific wheels (especially for GPU support). If `pip install` fails on one of these, check the project's own installation docs for your OS/GPU before reporting it as a bug in this project.

## Usage

Run the script from the command line, pointing it at a scanned PDF:

```bash
python pdfrestorer.py --input path/to/book.pdf --output path/to/output_folder
```

### Arguments

| Argument     | Required | Default                   | Description                                       |
| ------------ | -------- | ------------------------- | ------------------------------------------------- |
| `--input`  | Yes      | —                        | Path to the input scanned PDF file                |
| `--output` | No       | `.` (current directory) | Directory where the corrected files will be saved |

### Output

For an input file named `book.pdf`, the script produces, inside the output directory:

- `book_corrected.pdf`
- `book_corrected.epub`

It also creates a temporary `./output/imgs` folder (relative to where you run the script) to hold images extracted during OCR; this folder is cleared at the start of each run.

### Example

```bash
python pdfrestorer.py --input ./scans/don_quijote.pdf --output ./restored
```

This will generate `./restored/don_quijote_corrected.pdf` and `./restored/don_quijote_corrected.epub`.

## Notes and limitations

- The OCR language is currently hardcoded to Spanish (`lang="es"`) in `pdfrestorer.py`. Change this in the script if you need another language.
- Processing time depends heavily on the number of pages and the speed of local LLM inference.
- The correction step relies on a general-purpose small LLM, so it isn't perfect — always review the output for critical use cases.

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)** — see the [`LICENSE`](./LICENSE) file for the full text. In short, GPL-3.0 lets anyone use, modify, and redistribute this project, as long as derivative works are also distributed under the GPL and made available with their source code.

### Why GPL-3.0, and how it interacts with dependencies

This project depends on **EbookLib**, which is licensed under the **GNU Affero General Public License v3 (AGPL-3.0)**, a stricter copyleft license that also covers network use (running the software as a service). GPL-3.0 and AGPL-3.0 are compatible in one direction: **GPL-3.0 §13 explicitly permits combining a GPL-3.0-licensed work with an AGPL-3.0-licensed work**, provided that the combined work as a whole then follows AGPL-3.0's network-interaction terms (roughly: if you run this project as a network service, users interacting with it over the network must be offered the source code, not just users who receive a distributed copy). Since this project's `LICENSE` is GPL-3.0, this combination is permitted — but be aware that, in effect, distributing or hosting this project means honoring the **stricter (AGPL) terms**, not just plain GPL terms.

Practically, this means:

- You're free to use, modify, and redistribute this project under GPL-3.0 terms.
- If you also run it as a network service (e.g. a web app wrapping this script), you should make the source available to users of that service, per AGPL §13.
- This README is not legal advice — for anything beyond personal/internal use, especially commercial deployment, consult a lawyer.

### Other key direct dependencies

| Library                  | Used for                    | License                            |
| ------------------------ | --------------------------- | ---------------------------------- |
| PaddleOCR / PaddlePaddle | OCR / layout extraction     | Apache License 2.0                 |
| llama-cpp-python         | Running the local LLM       | MIT License                        |
| Python-Markdown          | Markdown → HTML conversion | BSD-3-Clause                       |
| xhtml2pdf                | HTML → PDF export          | Apache License 2.0                 |
| EbookLib                 | HTML → EPUB export         | **GNU AGPL-3.0** (see above) |

Apache-2.0, MIT, and BSD-3-Clause are all permissive licenses: they allow commercial and private use, modification, and redistribution, generally only requiring that you keep the original copyright/license notice and (for Apache-2.0) a notice of changes.

### The rest of `requirements.txt`

`requirements.txt` includes many additional packages (e.g. `numpy`, `pandas`, `langchain`, `opencv-contrib-python`, `pyHanko`, `reportlab`, etc.) that are transitive dependencies of the libraries above rather than things this project imports directly. Most are permissively licensed (MIT, BSD, or Apache-2.0), but this hasn't been individually verified here. **If you plan to redistribute this project — especially commercially — run a license audit over the full dependency tree** (a tool like [`pip-licenses`](https://pypi.org/project/pip-licenses/) can generate this automatically) rather than relying solely on this table.

### The Qwen2.5-3B-Instruct model

The model downloaded at runtime (`Qwen/Qwen2.5-3B-Instruct-GGUF`) has its own license terms set by its publisher on Hugging Face, separate from the Python package licenses above. Check the model's page on Hugging Face for the current terms before using it in a commercial product.
