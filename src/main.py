import json
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph.state import RunnableConfig
from pydantic import ValidationError
from rich import print

from graph import build_graph
from prompts import HUMAN_PROMPT, SYSTEM_PROMPT


def _content_to_text(content: str | list[str | dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                txt = item.get("text", "")
                if txt and txt.strip():
                    parts.append(txt)

                elif (
                    isinstance(item.get("content", None), str)
                    and item["content"].strip()
                ):
                    parts.append(item["content"])
        return "\n".join(parts)
    return str(content)


def main() -> None:
    config = RunnableConfig(configurable={"thread_id": 1})
    graph = build_graph()

    messages = [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(HUMAN_PROMPT),
    ]
    result = graph.invoke({"messages": messages}, config=config)

    final_message = result["messages"][-1]
    if isinstance(final_message, AIMessage):
        content = final_message.content
        raw_text: str = _content_to_text(content)
        print(content)
        try:

            parsed = JsonOutputParser().invoke(raw_text)

            json_path = Path(__file__).parent / "final_output.json"

            with json_path.open("w", encoding="utf-8") as file:
                json.dump(parsed, file, indent=4, ensure_ascii=False)

        except ValidationError as e:
            print(f"Errro ao parsear a resposta JSON: {e}")
            print(f"Conteúdo bruto da resposta: {content}")

    else:
        print("content não foi parsable.")
        return


if __name__ == "__main__":
    start = time.perf_counter()
    main()
    end = time.perf_counter()
    print(f"Execution time: {end - start:.2f} seconds")
    # expected time:  ~1165 seconds
