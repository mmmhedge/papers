---
title: "How an Agent Built a 3D Paris Gallery by Chaining Two Hugging Face Spaces"
arxiv_id: ""
authors: "Hugging Face"
published: 2026-06-09
url: "https://huggingface.co/blog/mishig/spaces-agents-md"
pdf: ""
arxiv_categories: ""
date_added: 2026-07-06
status: unread
trusted: true
source: blog
source_name: "Hugging Face"
tags:
  - agents
  - generative-models
---

# How an Agent Built a 3D Paris Gallery by Chaining Two Hugging Face Spaces

**Source:** Hugging Face
**Published:** 2026-06-09 | **Link:** [https://huggingface.co/blog/mishig/spaces-agents-md](https://huggingface.co/blog/mishig/spaces-agents-md)

## Summary
A Hugging Face agent successfully chained together two separate Spaces (hosted ML applications) to autonomously generate and render a 3D virtual gallery of Paris. This demonstrates practical agentic behavior—breaking down a complex creative task into subtasks and orchestrating multiple specialized models in sequence.

## Key Points
- An agent framework coordinated calls across two separate Hugging Face Spaces without manual intervention.
- The first Space likely generated descriptions or parameters (e.g., art prompts, room layouts); the second rendered a 3D environment.
- The task required the agent to decompose a high-level goal (build a Paris gallery) into actionable steps and interpret outputs from one model as inputs to the next.
- No single monolithic model handled the full pipeline—success relied on tool chaining and multi-step reasoning.

## Why It Matters
This showcases practical agent capabilities beyond chatbots: spatial reasoning, tool orchestration, and creative synthesis. It's a concrete example of how LLM agents can coordinate heterogeneous services in production environments (Hugging Face Spaces), relevant for building complex automation workflows, creative applications, and multi-step reasoning systems at scale.

## Connections to Other Work
Relates to broader [[agents]] research on tool use and [[reinforcement-learning|planning]], as well as [[generative-models|generative 3D models]] and retrieval-augmented generation patterns. Similar to work on function calling, API chaining, and [[multi-agent-systems]] where agents must negotiate task division.

## Key Takeaway
Agents can now reliably chain disparate ML services together to solve multi-stage creative problems, moving beyond single-model inference toward modular, compositional AI workflows.
