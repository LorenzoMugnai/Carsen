# What is MCP?

MCP stands for Model Context Protocol. It is a standard way for AI tools to ask external systems for context or actions. In Carsen, MCP lets an assistant ask questions such as "find the function that configures retrieval" or "read the source around this citation".

```mermaid
sequenceDiagram
    participant User
    participant Client as LLM client
    participant Carsen as Carsen MCP server
    participant Store as Carsen indexes
    User->>Client: Ask a question
    Client->>Carsen: Request relevant context through MCP
    Carsen->>Store: Retrieve cited chunks
    Store-->>Carsen: Context and metadata
    Carsen-->>Client: Cited retrieval results
    Client-->>User: Final answer grounded in retrieved context
```

## Why it helps

Without MCP, an assistant often only sees the text you paste into the chat. With MCP, the assistant can request relevant project context from Carsen when it needs it.

## Important boundary

Carsen retrieves context. It does not decide which LLM writes the final answer. That keeps the retrieval layer independent from any one model provider.
