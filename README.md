# Wikipedia XML Dump Graph Analyzer

A parallelized Wikipedia XML dump processor that extracts the article link graph and computes graph-based statistics such as PageRank, strongly connected components, and community structure.

The project leverages Wikipedia multistream dumps to process articles concurrently while keeping memory usage bounded. Links are filtered against a shared title index and stored as sharded edge files, which are later merged into a global graph for analysis.

## Features

- Parallel processing of Wikipedia multistream XML dumps
- Memory-aware chunk scheduling
- Shared-memory title lookup for efficient link validation
- Article statistics and category extraction
- Directed link graph construction
- Degree rankings and PageRank analysis
- Strongly connected component (SCC) condensation
- Louvain community detection
- Per-community category summaries

## Architecture

The pipeline consists of two phases:

1. **Parallel extraction**
   - Parse dump streams in parallel
   - Extract article metadata, links, and categories
   - Store intermediate edge and metadata files

2. **Graph analysis**
   - Merge edge files into a global graph
   - Compute PageRank and degree statistics
   - Find SCCs and perform community detection
   - Generate reports and clean up temporary artifacts

## Requirements

- Python 3.10+
- NumPy
- lxml
- python-igraph

Install dependencies:

```bash
pip install numpy lxml igraph
```

## Usage

```bash
python main.py [options]
```

### Arguments

| Option | Description | Default |
|----------|------------|---------|
| `-f`, `--file` | Path to Wikipedia multistream XML dump | `WIKI_DUMP` |
| `-i`, `--index` | Path to dump index file | `WIKI_INDEX` |
| `-c`, `--chunk_size` | Number of pages per processing chunk | `10000` |
| `-m`, `--max_pending_mb` | Approximate memory budget for queued chunks (MB) | `2048` |

### Example

```bash
python main.py \
    --file enwiki-latest-pages-articles-multistream.xml.bz2 \
    --index enwiki-latest-pages-articles-multistream-index.txt.bz2 \
    --chunk_size 10000 \
    --max_pending_mb 4096
```

## Main Components

| File | Purpose |
|--------|---------|
| `main.py` | Program entry point |
| `reader_func.py` | Index parsing and parallel orchestration |
| `worker_func.py` | Per-process page processing |
| `helpers_func.py` | Wikitext cleanup and link extraction |
| `decorators.py` | Plugin pipeline |
| `serializer.py` | Worker artifact serialization |
| `aggregator.py` | Global result aggregation |
| `graph_analysis.py` | Graph construction and analytics |
| `memory_throttle.py` | Memory-aware task scheduling |
| `file_manager.py` | Logging and cleanup |

## Processing Pipeline

```
Index scan
      ↓
Shared title set creation
      ↓
Parallel page parsing
      ↓
Link/category extraction
      ↓
Per-worker edge serialization
      ↓
Global graph construction
      ↓
PageRank + SCC + Louvain
      ↓
Report generation
```

## Technologies

- **lxml** – streaming XML parsing
- **bz2** – Wikipedia multistream decompression
- **multiprocessing** – parallel execution
- **shared_memory** – zero-copy title lookup
- **NumPy** – compact numerical buffers
- **igraph** – graph algorithms and community detection

## Output

The program produces:

- Link graph edges
- Article and category statistics
- PageRank rankings
- Strongly connected component information
- Community detection results
- Summary report (`report.txt`)
