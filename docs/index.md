# Carsen

<section class="carsen-hero" markdown>
<div class="carsen-hero__copy" markdown>
<p class="carsen-kicker">Local-first MCP knowledge engine</p>
<img src="assets/logo_text.png" alt="Carsen" class="carsen-wordmark">

Carsen indexes your code and documents into isolated knowledge instances, then retrieves cited context so an LLM-capable client can answer with better grounding.
</div>

<div class="carsen-hero__art" markdown>
<img src="assets/logo_character.png" alt="Carsen, the librarian" class="carsen-hero__logo">
</div>

<div class="carsen-cta-row" markdown>
[Start the quickstart](quickstart.md){ .md-button .md-button--primary }
[Connect to an LLM](llm-integration.md){ .md-button }
[Learn the concepts](concepts.md){ .md-button }
</div>
</section>

## The problem

When an LLM or an AI agent has to answer questions about *your* code, papers and notes, it usually does one of three unsatisfying things:

- **guesses from training data** and quietly invents the specifics — a function signature, a config key, a parameter bound, a number;
- **has the whole file pasted into its context**, which is wasteful and stops working once the corpus is large;
- **calls a hosted RAG service**, which means shipping your material to a third party and trusting citations you cannot check.

Carsen is the missing middle: index your sources into isolated, on-disk knowledge bases, and get back the few passages that actually answer a query, each with a citation you can open — source path, line span, and a commit-pinned link where one exists. It serves those results over MCP, so the client and the model stay your choice, and nothing leaves your machine unless you configure it to.

## Why Carsen

<div class="carsen-card-grid" markdown>
<div class="carsen-card" markdown>
### Local-first
Keep configuration, sources and indexed state on your own machine by default.
</div>

<div class="carsen-card" markdown>
### Isolated instances
Create one named knowledge base per project, course, lab or corpus.
</div>

<div class="carsen-card" markdown>
### MCP serving
Expose retrieval to MCP-capable clients without binding Carsen to one model provider.
</div>

<div class="carsen-card" markdown>
### Cited retrieval
Return context with source metadata rather than fabricated references.
</div>
</div>

## How it works

<div class="carsen-flow" markdown>

1. Create a Carsen knowledge instance for your material.
2. Index code, notes, papers or documentation into canonical chunks.
3. Search from the terminal to confirm retrieval works.
4. Serve the instance over MCP.
5. Let your LLM client ask Carsen for cited context.

</div>

## Ask an LLM about Carsen itself

Carsen can create a local self-reference instance for its own docs and source code:

```bash
carsen init-self --index
carsen search carsen-self "How do I connect Carsen to an LLM?"
carsen serve carsen-self --transport stdio
```

## Explore the docs

- [Quickstart](quickstart.md)
- [Connect to an LLM](llm-integration.md)
- [Core concepts](concepts.md)
- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Knowledge instances](knowledge-instances.md)
- [Indexing](indexing.md)
- [Retrieval](retrieval.md)
- [Citations](citations.md)
- [MCP](mcp.md)
- [Deployment](deployment.md)
- [Security](security.md)
- [Development](development.md)
- [Testing](testing.md)
- [Extending](extending.md)
- [Troubleshooting](troubleshooting.md)

## The name

The mascot is Carsen, a librarian. The name is a quiet nod to a certain fictional librarian — the one with a wall of academic degrees who, whatever you ask, can tell you the exact shelf, the exact volume and the exact page. That is the job description here: Carsen does not write your final answer, it just always knows where the answer lives and never makes up a citation. The pixel-art librarian is our own.
