from pathlib import Path
import time
from tracemalloc import start
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from rich import print, print_json
from langchain_core.output_parsers import JsonOutputParser

from graph import build_graph
from prompts import SYSTEM_PROMPT

import json

def main() -> None:
    config = RunnableConfig(configurable={"thread_id": 1})
    graph = build_graph()

    messages = [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(
        "Extraia o texto do PDF no caminho 'pdfs/exemplo.pdf' entre as páginas 1 e 3."
    )
    ]
    # current_message = [human_message]
    result = graph.invoke({"messages": messages}, config=config)

    content = result["messages"][-1].content
    # print(content[-1]['text'])

    # print(content)
    try:
        parsed = JsonOutputParser().invoke(content[-1]['text'])  # passe a string, não um dict
        # print_json(data=parsed)
        JSON_PATH = Path(__file__).parent / "final_output.json"
        with JSON_PATH.open("w", encoding="utf-8") as file:
            json.dump(parsed, file, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Errro ao parsear a resposta JSON: {e}")
        print(f"Conteúdo bruto da resposta: {content}")


if __name__ == "__main__":
    start = time.perf_counter()
    main()
    end = time.perf_counter()
    print(f"Execution time: {end - start:.2f} seconds")
