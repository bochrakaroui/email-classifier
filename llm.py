"""Seul module connaissant le transport Ollama et sa reprise bornée."""

import json
import time
from typing import TypeVar

import httpx
from ollama import Client, ResponseError
from pydantic import BaseModel, ValidationError

DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 900}
T = TypeVar("T", bound=BaseModel)


class ErreurTraitement(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.analyse = None


class OllamaLLM:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = "http://localhost:11434",
                 timeout: float = 180, client=None):
        self.model = model
        self.client = client if client is not None else Client(host=host, timeout=timeout)
        self.appels: list[dict] = []

    def generer(self, messages: list[dict], schema: type[T], *, contexte: dict | None = None) -> T:
        """Deux essais maximum, uniquement si le contenu JSON est invalide."""
        schema_json = schema.model_json_schema()
        conversation = [dict(m) for m in messages]
        conversation[0]["content"] += "\nSchéma JSON : " + json.dumps(schema_json, ensure_ascii=False)
        for tentative in (1, 2):
            debut = time.perf_counter()
            try:
                reponse = self.client.chat(
                    model=self.model, messages=conversation, format=schema_json,
                    options=OPTIONS, stream=False, keep_alive="10m",
                )
            except httpx.TimeoutException as exc:
                raise ErreurTraitement("timeout", "Délai Ollama dépassé") from exc
            except (ConnectionError, httpx.TransportError) as exc:
                raise ErreurTraitement("connexion", "Ollama inaccessible ; vérifier ollama serve et --host") from exc
            except ResponseError as exc:
                code = "modele_indisponible" if exc.status_code == 404 else "ollama"
                raise ErreurTraitement(code, f"Ollama HTTP {exc.status_code} : {exc.error}") from exc
            self.appels.append({
                "schema": schema.__name__, "tentative": tentative,
                "secondes": round(time.perf_counter() - debut, 3),
                "eval_count": reponse.eval_count,
                "eval_duration_ns": reponse.eval_duration,
                "load_duration_ns": reponse.load_duration,
            })
            contenu = reponse.message.content or ""
            try:
                return schema.model_validate_json(contenu, context=contexte)
            except ValidationError as exc:
                raisons = "; ".join(e["msg"] for e in exc.errors(include_input=False))[:500]
                if tentative == 2:
                    raise ErreurTraitement(
                        "sortie_invalide", f"{schema.__name__} invalide après 2 essais : {raisons}",
                    ) from exc
                conversation.append({"role": "assistant", "content": contenu})
                conversation.append({"role": "user", "content":
                    "La sortie ne respecte pas le schéma. Corrige uniquement le JSON selon le schéma système. " + raisons})
        raise AssertionError("Boucle de reprise terminée sans résultat")
