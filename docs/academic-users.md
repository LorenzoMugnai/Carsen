# Carsen for academic groups

Carsen is designed for research environments where knowledge is spread across code repositories, lab notes, technical documentation, papers, proposals and shared folders. The goal is not to replace careful reading. The goal is to make relevant context easier to retrieve, cite and inspect.

## Why this matters in research

Research projects often accumulate knowledge in many places:

- analysis scripts;
- instrument documentation;
- simulation outputs and notes;
- internal reports;
- student handover documents;
- project-specific conventions that are not published anywhere.

Carsen indexes those materials into a local knowledge instance. An MCP-capable assistant can then ask Carsen for relevant context instead of guessing from memory.

## A useful analogy

Imagine a library catalogue for your research project. The catalogue does not write the book for you. It tells you which shelf, page and paragraph are relevant. Carsen plays a similar role for AI tools: it retrieves context and citations, while the assistant or human still interprets the result.

## Recommended lab workflow

1. Create one Carsen instance per project, paper, instrument or collaboration.
2. Keep private projects in separate instances.
3. Index code and documentation after meaningful changes.
4. Use citations to verify every important answer.
5. Avoid exposing HTTP services publicly unless you understand the security implications.

## What Carsen is not

- It is not a magic source of truth.
- It is not a replacement for version control or data management.
- It is not an LLM provider.
- It does not remove the need to verify scientific claims.

## Good first use cases

- Searching a large codebase for relevant functions.
- Helping new students understand project documentation.
- Retrieving instrument or pipeline notes during analysis.
- Keeping separate knowledge bases for separate collaborations.
