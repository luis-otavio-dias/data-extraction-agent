import asyncio
from pathlib import Path

from langchain.tools import BaseTool, tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pypdf import PdfReader

from utils import load_google_generative_ai_model

exam_pdf_path = Path(__file__).parent.parent / "pdfs" / "prova.pdf"
answer_key_pdf_path = Path(__file__).parent.parent / "pdfs" / "gabarito.pdf"


def _pdf_extract_text_impl(
    pdf_path: Path = exam_pdf_path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """
    Extrai o texto de um arquivo PDF entre as páginas start_page e end_page.
    Retorna texto extraído como uma string contendo o texto de cada página
    separada por quebras de linha e identificada pelo número da página.
    Args:
        pdf_path (Path): Caminho para o arquivo PDF.
        start_page (int): Página inicial (inclusiva).
        end_page (int): Página final (exclusiva).
    Returns:
        str: Texto extraído do PDF.
    """
    text = ""
    pages_text = {}

    with pdf_path.open("rb") as pdf:
        reader = PdfReader(pdf)
        total_pages = len(reader.pages)

        if start_page is None or start_page < 0:
            start_page = 0
        if end_page is None or end_page > total_pages:
            end_page = total_pages
        if start_page >= end_page:
            return ""

        for page in reader.pages[start_page:end_page]:
            page_no = reader.pages.index(page) + 1
            page_text = page.extract_text()
            pages_text[page_no] = page_text
            text += f"\n\n --- Page {page_no} --- \n\n{page_text}"

    return text


@tool
def pdf_extract_jpegs(
    pdf_path: Path,
    output_dir: Path = Path("media_images"),
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """
    Extrai imagens JPEG de um arquivo PDF e as salva em um diretório
    especificado.

    Args:
        pdf_path (Path): Caminho para o arquivo PDF.
        output_dir (Path): Diretório onde as imagens extraídas serão salvas.
        start_page (int): Página inicial (inclusiva).
        end_page (int): Página final (exclusiva).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with pdf_path.open("rb") as pdf:
        reader = PdfReader(pdf)
        total_pages = len(reader.pages)

        if start_page is None or start_page < 0:
            start_page = 0
        if end_page is None or end_page > total_pages:
            end_page = total_pages
        if start_page >= end_page:
            return "Intervalo de páginas inválido."

        saved = 0
        for page_index in range(start_page, end_page):
            page = reader.pages[page_index]
            for image_file_object in page.images:
                if image_file_object.name.find(".jpg") != -1:
                    img_name = f"page_{page_index+1}_{image_file_object.name}"

                    out_path = output_dir / img_name
                    with out_path.open("wb") as fp:
                        fp.write(image_file_object.data)
                    saved += 1

    if saved == 0:
        return "Nenhuma imagem JPEG encontrada no intervalo especificado."
    return f"{saved} imagens JPEG extraída(s) em '{output_dir.resolve()}'"


@tool
def extract_exam_pdf_text(
    exam_pdf_path: Path,
    answer_key_pdf_path: Path,
    exam_start_page: int | None = None,
    exam_end_page: int | None = None,
) -> str:
    """
    Extrai o texto de um PDF de prova e de um PDF de gabarito e salva-o em
    um arquivo .txt temporário. Retorna o caminho (Path) para esse arquivo
    temporário. O caminho de arquivo resultante deve ser usado como entrada
    para structure_questions.

    Returns:
        str: Caminho do arquivo onde o texto extraído foi salvo.
    """

    exam_text = _pdf_extract_text_impl(
        exam_pdf_path, start_page=exam_start_page, end_page=exam_end_page
    )

    if answer_key_pdf_path.exists():
        answer_key_text = _pdf_extract_text_impl(pdf_path=answer_key_pdf_path)
        exam_text += "\n\n--- Gabarito ---\n\n" + answer_key_text

    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / "extracted_text.txt"

    with temp_file.open("w", encoding="utf-8") as f:
        f.write(exam_text)

    return str(temp_file)


@tool
async def structure_questions(extracted_text_path: str) -> str:
    """
    Recebe a string de texto longa e completa gerada pela ferramenta
    extract_exam_pdf_text e a analisa, extraindo as questões em formato JSON.
    Esta ferramenta NÃO deve ser usada com nenhum outro texto.
    Args:
        extracted_text_path (str): O caminho do arquivo .txt gerado pela
        ferramenta extract_exam_pdf_text.
    Returns:
        str: Array JSON com as questões estruturadas.
    """
    extracted_text = await asyncio.to_thread(
        Path(extracted_text_path).read_text, encoding="utf-8"
    )

    llm = load_google_generative_ai_model()
    parser = JsonOutputParser()
    format_instructions = parser.get_format_instructions()

    system = (
        "You are an expert in extracting and structuring exam questions into a"
        " JSON format. Given the text of an exam and its answer key, "
        " your task is identify each question along with its possible answers"
        " and the correct answer from the answer key. "
        "Structure the output as a JSON array where each element represents a"
        " question with its details."
        "Produce ONLY a JSON array, one object per question. No code fences.\n"
        f"{format_instructions}"
    )

    schema_hint = """
Follow this structure exactly for each question:
    - Question and question number
    - Whether there is an image associated with the question (true/false)
    - The passage text:
        - Some questions may have a passage before the statement that should
        be included.
        - Add break lines (\n) as needed to preserve paragraph structure.
        - If there is no passage, return an empty string for this field.
        - May contain the source of the passage text.
        - The source of the passage text must be stored in the Sources field,
        following the instructions provided.
        - The source of the passage should not be included in the passage text
        itself.
    - Sources:
        - A list of strings indicating the source of the passage text or the
        source of an image.
        - Even if the source is for an image, the tool 'pdf_extract_jpegs'
         must be called to extract and save the image files.
        - If there is no source, return an empty list for this field.
        - May be an URL or a book reference, article, textbook, etc.
        - If is an URL:
            - Extract the link and store it as it is.
            - Extract the access date. Identify by phrases like this stucture
            "text: date".
            - Store only the content as it is. Without the preceding
             phrase "text: "
        - If is a book reference, article, textbook, etc.:
            - Extract and store is as it is.
    - Statement
    - Options (A, B, C, D, E)
    - Correct option (A, B, C, D, E)

Output Instructions:
- Return only a JSON array with one object per question (no code fences).
- Follow this structure exactly:
{
    "question": str,
    "image": bool,
    "passage_text": str,
    "sources": [str],
    "statement": str,
    "options": {
        "A": str,
        "B": str,
        "C": str,
        "D": str,
        "E": str
    },
    "correct_option": str
}
""".strip()

    messages = [
        SystemMessage(system),
        HumanMessage(
            f"{schema_hint}\n\nEXAM_TEXT_START\n{extracted_text}\n\nEXAM_TEXT_END"
        ),
    ]

    ai = await llm.ainvoke(messages)

    content = ai.content

    return str(content).strip()


TOOLS: list[BaseTool] = [
    pdf_extract_jpegs,
    extract_exam_pdf_text,
    structure_questions,
]
TOOLS_BY_NAME: dict[str, BaseTool] = {tool.name: tool for tool in TOOLS}
