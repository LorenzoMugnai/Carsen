# Citations

Citations are generated from chunk or result metadata. The formatter does not invent missing source details.

## Code citations

When repository and commit metadata are present, code citations use:

```text
repository@commit:path:start-end
```

Without repository metadata, the formatter falls back to `path:start-end` or the chunk/source identifier.

## Document citations

Document citations use available path, page and section metadata:

```text
path:p.12 §Heading
```

If page or section metadata is absent, the formatter omits that part. Unknown locations are reported as `unknown source`.
