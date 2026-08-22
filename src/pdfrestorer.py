from paddleocr import PPStructureV3
from pathlib import Path
from llama_cpp import Llama
import re
import os
from ebooklib import epub
import markdown
from xhtml2pdf import pisa
import shutil
import argparse

def create_file(input_path, output_dir):
    imgs_dir = Path("./output/imgs")
    if imgs_dir.exists():
        shutil.rmtree(imgs_dir)
    imgs_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_path)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.")
        return
    base_name = input_path.stem

    pipeline = PPStructureV3(
        lang="es",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
    )

    output = pipeline.predict(str(input_path))
    for res in output:
        res.save_to_markdown(save_path="./output")

    def page_num(p):
            m = re.search(r"Page (\d+)", p.stem)
            return int(m.group(1)) if m else 0

    pages = []
    for file in sorted(Path("./output").glob("*.md"), key=page_num):
        pages.append(file.read_text(encoding="utf-8"))
        file.unlink()

    unified_pages = "\n\n".join(pages)

    def chunk_with_overlap(text, max_words=700, overlap_paragraphs=1):
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for paragraph in paragraphs:
            paragraph_length = len(paragraph.split())
            if current_length + paragraph_length > max_words and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = current_chunk[-overlap_paragraphs:] if overlap_paragraphs > 0 else []
                current_length = sum(len(p.split()) for p in current_chunk)

            current_chunk.append(paragraph)
            current_length += paragraph_length

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    llm = Llama.from_pretrained(
        repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        filename="qwen2.5-3b-instruct-q5_k_m.gguf",
        verbose=False,
        n_ctx=4096,
        n_gpu_layers=-1,
        n_threads=os.cpu_count(),
        n_batch=512,
    )

    system_prompt = """
    Eres un editor experto en restauración de textos antiguos digitalizados por OCR.
    Recibirás un bloque de texto con dos secciones: [CONTEXTO ANTERIOR] (ya corregido,
    solo para referencia de continuidad) y [TEXTO A CORREGIR] (lo que debes arreglar).

    Reglas estrictas:
    1. Corrige SOLO el contenido de [TEXTO A CORREGIR]. No reescribas ni repitas el
       [CONTEXTO ANTERIOR] en tu respuesta.
    2. Une las palabras que quedaron cortadas al final de línea por guiones (ej. "incapa. ces" -> "incapaces").
    3. Reconstruye los párrafos continuos eliminando saltos de línea innecesarios dentro de la misma oración.
    4. Corrige caracteres erróneos del OCR (ej. "Ia" -> "la", "asf" -> "así", puntos sobrantes como "en:el .asalto").
    5. Mantén la estructura de títulos en Markdown (#, ##) y las etiquetas HTML de imágenes (<div...>) intactas.
    6. NO resumas, NO agregues explicaciones ni introducciones. Responde ÚNICAMENTE con el texto en Markdown corregido.
    """

    chunks = chunk_with_overlap(unified_pages, max_words=700, overlap_paragraphs=1)

    corrected_chunks = []
    context_tail = ""

    for i, chunk in enumerate(chunks):
        user_content = f"[CONTEXTO ANTERIOR]\n{context_tail}\n\n[TEXTO A CORREGIR]\n{chunk}"

        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=2048,
            repeat_penalty=1.2,
        )

        choice = response["choices"][0]
        if choice["finish_reason"] == "length":
            print(f"Warning: Chunk {i+1} response was truncated. Consider increasing max_tokens.")

        result = choice["message"]["content"].strip()
        corrected_chunks.append(result)
        context_tail = " ".join(result.split()[-100:])

    corrected_text = "\n\n".join(corrected_chunks)

    def export_to_epub(html_content, output_path="docFinal.epub", images_base="./output"):
        book = epub.EpubBook()
        book.set_identifier("id_doc_final")
        book.set_title(base_name)
        book.set_language("es")

        img_paths = re.findall(r'src="([^"]+)"', html_content)
        for img_rel_path in set(img_paths):
            full_path = Path(images_base) / img_rel_path
            if full_path.exists():
                img_item = epub.EpubImage(
                    uid=img_rel_path.replace("/", "_"),
                    file_name=img_rel_path,
                    media_type="image/png",
                    content=full_path.read_bytes(),
                )
                book.add_item(img_item)

        chapter = epub.EpubHtml(
            title="Content", file_name="chap_1.xhtml", lang="es"
        )
        chapter.content = f"<html><body>{html_content}</body></html>"
        book.add_item(chapter)

        book.toc = (chapter,)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", chapter]

        epub.write_epub(output_path, book)


    def export_to_pdf(html_content, output_path="docFinal.pdf", images_base="./output"):
        def link_callback(uri, rel):
            if uri.startswith("http"):
                return uri
            path = os.path.join(os.path.abspath(images_base), uri)
            return path

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4;
                    margin: 20mm;
                }}
                body {{
                    font-family: serif;
                    font-size: 11pt;
                    line-height: 1.6;
                }}
                h1, h2, h3 {{
                    font-family: sans-serif;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        with open(output_path, "wb") as pdf_file:
            pisa.CreatePDF(full_html, dest=pdf_file, link_callback=link_callback)

    html_content = markdown.markdown(corrected_text, extensions=["tables", "fenced_code"])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
        
    export_to_pdf(html_content, str(output_dir / f"{base_name}_corrected.pdf"))
    export_to_epub(html_content, str(output_dir / f"{base_name}_corrected.epub"))

    print("Files generated correctly")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a PDF document and generate corrected EPUB and PDF files.")
    parser.add_argument("--input", type=str, required=True, help="Path to the input PDF file.")
    parser.add_argument("--output", type=str, default=".", help="Directory to save output files.")
    args = parser.parse_args()

    create_file(args.input, args.output)