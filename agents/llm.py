import json
import os


SYSTEM_PROMPT = (
    "Draft a concise, helpful customer-support reply. This is a draft only: "
    "do not take actions or claim that actions have been taken. Never promise, "
    "guarantee, or imply that a refund will be issued. If the customer asks "
    "about a refund, say that the request can be reviewed without promising an outcome."
)


def draft_support_reply(question, order_summary):
    model = os.environ.get("ANTHROPIC_MODEL")
    if not model:
        raise RuntimeError("ANTHROPIC_MODEL must be set")

    from anthropic import Anthropic

    if isinstance(order_summary, str):
        summary = order_summary
    else:
        summary = json.dumps(order_summary, ensure_ascii=True, default=str)

    response = Anthropic().messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Customer question:\n{question}\n\nOrder summary:\n{summary}",
            }
        ],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))