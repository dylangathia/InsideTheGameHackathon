"""The agents on Microsoft Agent Framework.

Three agents, each an Agent Framework `Agent` on the same Foundry deployment:

    narrator       writes the on-screen text for a key moment from the computed facts
    verifier       fact-checks the narrator's draft (after a deterministic number check in software)
    match_analyst  answers "Ask the match" questions with six read-only tools over the live match

The narrator and verifier are wired together as an Agent Framework `Workflow`:

    Request --> [narrator] --Draft--> [verifier] --pass--> output (verified text)
                    ^                     |
                    +---- rewrite once ---+--fail twice--> output (rejected: the template stays)

Used with Microsoft Foundry. Other providers (e.g. Groq's reasoning models, which need different
parameters) and the setting AGENT_FRAMEWORK=0 use the plain OpenAI SDK path with the same prompts.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable

log = logging.getLogger(__name__)

try:
    from agent_framework import Agent, Executor, FunctionTool, WorkflowBuilder, WorkflowContext, handler
    from agent_framework.openai import OpenAIChatCompletionClient

    AVAILABLE = True
except ImportError:  # the app still runs on the plain SDK path
    AVAILABLE = False


def enabled(llm) -> bool:
    return (AVAILABLE and getattr(llm, "provider", None) == "Foundry" and not getattr(llm, "reasoning", True)
            and os.getenv("AGENT_FRAMEWORK", "1") != "0")


def _client(llm, max_iterations: int | None = None):
    """An Agent Framework chat client on our existing Foundry connection (same endpoint, key and deployment)."""
    config = {"max_iterations": max_iterations} if max_iterations else None
    return OpenAIChatCompletionClient(model=llm.model, async_client=llm.client,
                                      function_invocation_configuration=config)


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in reply: {text[:80]!r}")
    return json.loads(text[start:end + 1])


async def run_json_agent(llm, name: str, instructions: str, user: str, max_tokens: int, temperature: float) -> dict:
    """One turn of a named agent (narrator or verifier) that replies with a JSON object."""
    agent = Agent(_client(llm), instructions, name=name)
    async with llm.sem:
        resp = await agent.run(user, options={"response_format": {"type": "json_object"}, "max_tokens": max_tokens,
                                              "temperature": temperature})
    return parse_json(resp.text or "{}")


# ---------------------------------------------------------------------------- narrator -> verifier workflow
@dataclass
class Request:
    payload: dict
    attempt: int = 1


@dataclass
class Draft:
    payload: dict
    out: dict | None
    attempt: int


@dataclass
class Outcome:
    out: dict | None
    status: str  # passed | passed_after_rewrite | rejected | failed
    problems: list[str] = field(default_factory=list)
    second: list[str] = field(default_factory=list)


Write = Callable[[dict], Awaitable["dict | None"]]
Check = Callable[[dict], Awaitable[list[str]]]

if AVAILABLE:
    class NarratorExecutor(Executor):
        def __init__(self, write: Write):
            super().__init__(id="narrator")
            self.write = write

        @handler
        async def handle(self, msg: Request, ctx: WorkflowContext[Draft, Outcome]) -> None:
            out = await self.write(msg.payload)
            if out is None and msg.attempt == 1:
                await ctx.yield_output(Outcome(None, "failed"))
                return
            await ctx.send_message(Draft(msg.payload, out, msg.attempt))

    class VerifierExecutor(Executor):
        def __init__(self, check: Check):
            super().__init__(id="verifier")
            self.check = check
            self.first: list[str] = []

        @handler
        async def handle(self, msg: Draft, ctx: WorkflowContext[Request, Outcome]) -> None:
            problems = await self.check(msg.out) if msg.out else ["no rewrite"]
            if not problems:
                status = "passed" if msg.attempt == 1 else "passed_after_rewrite"
                await ctx.yield_output(Outcome(msg.out, status, self.first))
            elif msg.attempt == 1:
                self.first = problems  # back to the narrator once, with the problems to fix
                await ctx.send_message(Request({**msg.payload, "rejected_draft": msg.out,
                                                "fix_these_problems": problems}, attempt=2))
            else:
                await ctx.yield_output(Outcome(msg.out, "rejected", self.first, problems))


async def narrate_and_verify(payload: dict, write: Write, check: Check) -> Outcome:
    """Run the narrator -> verifier workflow for one moment and one viewer profile."""
    narrator, verifier = NarratorExecutor(write), VerifierExecutor(check)
    workflow = (WorkflowBuilder(name="narrate_and_verify", start_executor=narrator)
                .add_edge(narrator, verifier).add_edge(verifier, narrator).build())
    result = await workflow.run(Request(payload))
    outputs = result.get_outputs()
    return outputs[-1] if outputs else Outcome(None, "failed")


# ---------------------------------------------------------------------------- match analyst
async def run_match_analyst(llm, system: str, question: str, specs: list[dict],
                            call_tool: Callable[[str, dict], dict], max_steps: int) -> str:
    """The "Ask the match" agent: Agent Framework runs the tool loop over our read-only match tools."""
    tools = []
    for spec in specs:
        fn = spec["function"]

        def invoke(_name=fn["name"], **kwargs):
            return json.dumps(call_tool(_name, kwargs), ensure_ascii=False)

        tools.append(FunctionTool(name=fn["name"], description=fn["description"], func=invoke,
                                  input_model=fn["parameters"]))
    agent = Agent(_client(llm, max_iterations=max_steps), system, name="match_analyst", tools=tools)
    async with llm.sem:
        resp = await agent.run(question, options={"max_tokens": 500, "temperature": 0.2})
    return (resp.text or "").strip()
