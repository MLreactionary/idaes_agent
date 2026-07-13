
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainChunk:
    domain: str
    path: str
    title: str
    text: str
    score: float = 0.0


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|\\d+(?:\\.\\d+)?", text.lower()))


def read_domain_file(path: Path) -> str:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, indent=2, sort_keys=True)

    return path.read_text(encoding="utf-8")


def load_domain_chunks(domain: str, root: Path | None = None) -> list[DomainChunk]:
    root = root or Path("knowledge/domains")
    domain_dir = root / domain

    if not domain_dir.exists():
        raise FileNotFoundError(f"Domain directory not found: {domain_dir}")

    chunks: list[DomainChunk] = []

    for path in sorted(domain_dir.iterdir()):
        if path.suffix not in {".md", ".json", ".txt"}:
            continue

        text = read_domain_file(path)
        title = path.stem.replace("_", " ").title()

        chunks.append(
            DomainChunk(
                domain=domain,
                path=str(path),
                title=title,
                text=text,
                score=0.0,
            )
        )

    return chunks


def score_chunk(prompt: str, chunk: DomainChunk) -> float:
    prompt_tokens = tokenize(prompt)
    chunk_tokens = tokenize(chunk.text + " " + chunk.title)

    if not prompt_tokens:
        return 0.0

    overlap = len(prompt_tokens & chunk_tokens)

    bonus = 0.0
    lowered = prompt.lower()

    domain_signals = [
        "blend",
        "mix",
        "formulation",
        "feed",
        "fuel",
        "ore",
        "protein",
        "fiber",
        "sulfur",
        "ash",
        "purity",
        "grade",
        "octane",
        "at least",
        "at most",
        "minimum",
        "maximum",
        "minimize cost",
    ]

    for signal in domain_signals:
        if signal in lowered and signal in chunk.text.lower():
            bonus += 2.0

    if "schema" in chunk.title.lower():
        bonus += 1.5

    if "pyomo" in chunk.title.lower():
        bonus += 1.0

    if "verifier" in chunk.title.lower():
        bonus += 1.0

    return float(overlap) + bonus


def retrieve_domain_chunks(prompt: str, domain: str, top_k: int = 4) -> list[DomainChunk]:
    chunks = load_domain_chunks(domain)

    scored = [
        DomainChunk(
            domain=chunk.domain,
            path=chunk.path,
            title=chunk.title,
            text=chunk.text,
            score=score_chunk(prompt, chunk),
        )
        for chunk in chunks
    ]

    scored.sort(key=lambda chunk: chunk.score, reverse=True)
    return scored[:top_k]


def build_domain_context(prompt: str, domain: str, top_k: int = 4) -> str:
    chunks = retrieve_domain_chunks(prompt=prompt, domain=domain, top_k=top_k)

    parts = [
        f"# Retrieved domain context for {domain}",
        "",
        f"User prompt: {prompt}",
        "",
    ]

    for chunk in chunks:
        parts.extend(
            [
                f"## Source: {chunk.title}",
                f"Path: {chunk.path}",
                f"Score: {chunk.score}",
                "",
                chunk.text.strip(),
                "",
            ]
        )

    return "\n".join(parts)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--domain", default="general_blend")
    parser.add_argument("--top-k", type=int, default=4)

    args = parser.parse_args()

    print(build_domain_context(args.prompt, domain=args.domain, top_k=args.top_k))


if __name__ == "__main__":
    main()
