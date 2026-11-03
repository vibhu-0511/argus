# P8-T01 notes: multi-agent research system and building effective agents

Read on 2026-11-03 (fetched in full by a web-fetch helper, then written up here in my own words; one short quote). Posts:

- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), Anthropic engineering, 2025-06-13. Called "post 1" below.
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), Anthropic engineering, 2024-12-19. Called "post 2". It carries a banner that much of its tooling has changed since then and points to a newer post on Claude Managed Agents; that newer post was not read.

The task row is owner-type [ME]: this is a learning task. These notes are a first pass for the owner to check against the posts. The owner should still read both posts.

## The token overhead the post claims

Post 1, section "Benefits of a multi-agent system":

| Claim | Number the post gives |
|---|---|
| A single agent compared with a chat interaction | about 4 times more tokens |
| A multi-agent system compared with a chat interaction | about 15 times more tokens |

The post says outright that these systems "burn through tokens fast" and that the task has to be worth the cost. The numbers are Anthropic's, for its own research feature, in 2025. They are not measured on a coding agent and not on Argus.

Related claims in the same section:

- On the BrowseComp benchmark, three things explained 95% of the performance variance, and token usage alone explained 80%. The other two were the number of tool calls and the choice of model.
- A lead agent (Opus 4) with subagents (Sonnet 4) beat a single Opus 4 agent by 90.2% on Anthropic's internal research eval. So the gain is real for research, and a large part of it is simply more tokens spent in parallel.
- Newer models raise the value of each token ("large efficiency multipliers"): upgrading the model can beat doubling the token budget.

## Where multi-agent pays and where it does not

From post 1 ("Benefits of a multi-agent system"):

| Pays | Does not pay |
|---|---|
| Breadth-first work that splits into independent directions (many searches at once) | Tasks where all agents need the same context |
| Information that does not fit in one context window | Tasks with many dependencies between the agents' steps |
| Many complex tools | Coding: the post names it as the example, because most coding tasks have fewer parts that can truly run in parallel than research does |
| Tasks valuable enough to justify roughly 15 times the tokens | Anything cheap or short |

The one quote I use: multi-agent systems fit badly where "all agents [must] share the same context". (post 1, same section, shortened)

From post 2 ("When (and when not) to use agents"): look for the simplest solution first. Agentic systems "often trade latency and cost for better task performance", and for many applications one well-built LLM call with retrieval and examples is enough. The post separates workflows (fixed code paths) from agents (the model steers). Orchestrator-workers is the pattern for tasks where the sub-tasks cannot be known in advance, with coding changes across unknown files as its example. It differs from plain parallelisation in that the split is decided at run time. Coding agents are called a good fit for agents because tests give a checkable answer (post 2, appendix on coding agents), but human review stays necessary.

## Lessons from post 1 that carry over

- **Teach the lead to scale effort.** Simple lookups need one agent and a few tool calls; the early system spawned dozens of subagents for easy questions. Put the rule in the prompt (post 1, prompt engineering section, principles on effort scaling).
- **Give each subagent a full brief:** objective, output format, tool guidance, boundaries. Short instructions made subagents duplicate each other's work.
- **Judge the outcome, not a fixed path.** Start with about 20 real queries; effect sizes are big early. A single LLM-judge call with a pass/fail was the most consistent with humans (section "Effective evaluation of agents").
- **Agents are stateful and errors compound.** Resume from checkpoints, trace decisions in production, roll out gradually (section "Production reliability and engineering challenges").
- **Subagents can write output to external storage and pass a reference back,** which saves tokens against copying text through the lead (appendix).
- Post 2's three principles: keep it simple, show the planning steps, and put effort into the agent-computer interface (tool descriptions and testing).

## What this means for the P8-T11 planner and subagents ablation

The keep rule for the ablation is: the planner/subagents variant stays only if it wins on **both** resolve rate **and** tokens per bug against the single-agent loop.

1. **Expect it to lose on tokens.** The post's own figure is 15 times a chat for multi-agent against 4 times for a single agent, so about 3.75 times a single agent. The Argus fix loop is a coding task with shared context (the repo map, the failing repro, the diff), which is the named bad fit. The default expectation is a higher tokens per bug, so the rule is hard to pass, and that is the point of the rule.
2. **A resolve-rate gain alone proves little.** Token use explained 80% of the variance on BrowseComp, so a planner that spends more tokens can win resolve rate just by spending. Requiring tokens per bug to go down too removes that explanation: a win has to come from structure, not from budget. Do not accept a gain on one axis as a keep.
3. **Count every agent.** The T11 criterion already says the total across all agents goes into the ledger. Planner calls, each subagent's calls and any retry count. Counting only the lead would hide most of the cost.
4. **Give each subagent a context budget and a full brief** (post 1 lessons above), and write a rule for the planner on how many sub-tasks a small bug deserves: one or two for a one-file fix, as in the post's effort-scaling guidance. Without it the planner may over-split small bugs.
5. **Use the same 20 tasks, the same model and the same wall of tools** for both rows, with Wilson 95% intervals (T12). With 20 tasks the interval is wide; a small difference will not be separable, and then the rule says to keep the single agent.
6. **Where it might win:** bugs touching several unknown files, where the orchestrator-workers pattern fits and the context of a single agent runs out. If the 20 tasks are mostly one-file bugs, the planner cannot show it. Say in the T12 report how many tasks were multi-file.

The post figures are Anthropic's and are not Argus numbers. Argus numbers come from T12 runs only.
