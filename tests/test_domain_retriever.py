
from app.domain_retriever import build_domain_context, retrieve_domain_chunks


def test_general_blend_retriever_returns_chunks_for_animal_feed_prompt():
    prompt = (
        "We need to produce exactly 1,000 kg of animal feed. "
        "Corn costs 0.30/kg and contains 9% protein and 2% fiber. "
        "Soybean meal costs 0.90/kg and contains 50% protein and 8% fiber. "
        "Final mix must contain at least 22% protein and at most 5% fiber. "
        "Minimize total cost."
    )

    chunks = retrieve_domain_chunks(prompt, domain="general_blend", top_k=3)

    assert len(chunks) == 3
    assert all(chunk.score >= 0 for chunk in chunks)
    assert any("schema" in chunk.path for chunk in chunks)
    assert any("protein" in chunk.text.lower() for chunk in chunks)


def test_general_blend_context_contains_key_modeling_rules():
    prompt = "Blend corn and soybean meal with protein at least 22 percent and fiber at most 5 percent."

    context = build_domain_context(prompt, domain="general_blend", top_k=5)

    assert "quality lower bound" in context.lower()
    assert "quality upper bound" in context.lower()
    assert "pyomo" in context.lower()
    assert "protein" in context.lower()
    assert "fiber" in context.lower()
