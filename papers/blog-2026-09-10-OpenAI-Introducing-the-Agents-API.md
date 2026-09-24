---
title: "Introducing the Agents API"
arxiv_id: ""
authors: "OpenAI"
published: 2026-09-10
url: "https://openai.com/index/introducing-the-agents-api"
pdf: ""
arxiv_categories: ""
date_added: 2026-09-24
status: unread
trusted: true
source: blog
source_name: "OpenAI"
tags:
  - agents
  - large-language-models
---

# Introducing the Agents API

**Source:** OpenAI
**Published:** 2026-09-10 | **Link:** [https://openai.com/index/introducing-the-agents-api](https://openai.com/index/introducing-the-agents-api)

## Summary
OpenAI has released the Agents API, a managed cloud service that enables developers to build and deploy autonomous agents with built-in orchestration, persistent sessions, and tool integration capabilities. This represents a shift toward making agentic AI systems more accessible and production-ready for enterprise use.

## Key Points
- **Managed Service Model**: The Agents API abstracts away infrastructure complexity, allowing developers to focus on agent behavior rather than deployment logistics.
- **Codex Orchestration**: Uses a code-based harness for coordinating agent actions, reasoning, and tool calls.
- **Long-Running Sessions**: Supports persistent state and multi-turn interactions, enabling agents to maintain context across extended workflows.
- **Tool Use**: Agents can call external APIs, databases, and functions as part of their decision-making process.
- **Cloud-Native**: Built as a managed service, handling scaling, monitoring, and reliability automatically.

## Why It Matters
Agentic systems represent the next frontier of LLM utility beyond simple chat interfaces. By packaging agent capabilities as a managed API, OpenAI lowers the barrier to entry for enterprises and startups building autonomous workflows—from customer support automation to research assistance to business process optimization. This accelerates real-world deployment of multi-step reasoning systems.

## Connections to Other Work
This builds on earlier work in [[agents|autonomous agents]], [[large-language-models|LLM-based systems]], and [[reinforcement-learning|decision-making frameworks]]. It competes with similar offerings from Anthropic (tools/function-calling) and open frameworks like LangChain. Related to broader trends in [[multi-agent-systems|multi-agent coordination]] and practical [[tool-use|tool grounding]].

## Key Takeaway
OpenAI launched a managed API for building cloud-based autonomous agents with orchestration and tool integration built in.
