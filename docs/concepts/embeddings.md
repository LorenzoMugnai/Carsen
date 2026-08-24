# What are embeddings?

An embedding is a list of numbers that represents the meaning of a piece of text. Similar texts should have vectors that are close to each other.

```mermaid
flowchart TD
    A["calibrate the detector"] --> B[Embedding model]
    C["instrument calibration steps"] --> B
    D["lunch menu"] --> B
    B --> E[Vectors]
    E --> F{Similarity search}
    F --> G[Calibration texts are near each other]
    F --> H[Unrelated texts are far away]
```

## Why this matters

Researchers rarely ask questions using exactly the same wording as the documentation. Embeddings let Carsen retrieve meaning-related passages, not only exact keyword matches.

## Limitations

Embeddings are useful but imperfect. They can miss important details or retrieve plausible but irrelevant text. Carsen therefore combines dense retrieval with sparse and exact retrieval paths, and returns citations so users can verify results.
