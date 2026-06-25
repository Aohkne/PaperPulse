"""LLM agent layer — each module owns one prompt-response task.

Import pattern:
    from backend.agent import outline as outline_agent
    themes = await outline_agent.run(query, papers)
"""
