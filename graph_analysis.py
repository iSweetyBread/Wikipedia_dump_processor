import os
import gc
import pickle
import igraph as ig
from collections import Counter, defaultdict
from file_manager import report_print
import numpy as np
from array import array

ARTIFACT_DIR = r'data/workers'


def load_edges(artifact_dir=ARTIFACT_DIR):
    edge_files = sorted(f for f in os.listdir(artifact_dir) if f.endswith("_edges.tsv"))
    print(f"Loading {len(edge_files)} edge files...")

    global_index: dict[str, int] = {}
    names: list[str] = []
    src_ids = array('i')
    dst_ids = array('i')

    for filename in edge_files:
        path = os.path.join(artifact_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                src, dst = line.split("\t", 1)

                src_idx = global_index.get(src)
                if src_idx is None:
                    src_idx = len(global_index)
                    global_index[src] = src_idx
                    names.append(src)

                dst_idx = global_index.get(dst)
                if dst_idx is None:
                    dst_idx = len(global_index)
                    global_index[dst] = dst_idx
                    names.append(dst)

                src_ids.append(src_idx)
                dst_ids.append(dst_idx)

    del global_index
    gc.collect()

    n_vertices = len(names)
    print(f"{n_vertices:,} unique vertices, {len(src_ids):,} edges")

    src_arr = np.frombuffer(src_ids, dtype=np.int32)
    dst_arr = np.frombuffer(dst_ids, dtype=np.int32)

    return src_arr, dst_arr, src_ids, dst_ids, names


def build_igraph(src_arr, dst_arr, n_vertices):
    graph = ig.Graph(n=n_vertices, directed=True)
    edge_array = np.column_stack((src_arr, dst_arr))
    if edge_array.dtype != np.int32:
        edge_array = edge_array.astype(np.int32)
    graph.add_edges(edge_array)
    return graph


def top_degrees(graph, names, top_n=20, mode="out"):
    if mode == "out":
        degrees = graph.outdegree()
    else:
        degrees = graph.indegree()

    deg_arr = np.asarray(degrees, dtype=np.int32)
    if top_n >= len(deg_arr):
        order = np.argsort(deg_arr)[::-1]
    else:
        part = np.argpartition(deg_arr, -top_n)[-top_n:]
        order = part[np.argsort(deg_arr[part])[::-1]]

    return [(names[i], int(deg_arr[i])) for i in order]


def pagerank_top_pages(graph, names, top_n=20, damping=0.85):
    print("Computing Page rank...")
    scores = graph.pagerank(damping=damping, directed=True)
    scores_arr = np.asarray(scores, dtype=np.float32)

    if top_n >= len(scores_arr):
        order = np.argsort(scores_arr)[::-1]
    else:
        part = np.argpartition(scores_arr, -top_n)[-top_n:]
        order = part[np.argsort(scores_arr[part])[::-1]]

    return [(names[i], float(scores_arr[i])) for i in order]


def detect_communities(scc, names):
    print("Condensing graph into SCC DAG...")
    membership = scc.membership
    condensed = scc.cluster_graph()
    condensed.vs["scc_id"] = range(condensed.vcount())

    print(f"Running Louvain on condensed graph ({condensed.vcount():,} SCC nodes)...")
    undirected = condensed.as_undirected()
    giant = undirected.connected_components().giant()
    condensed_communities = giant.community_multilevel()

    scc_to_vertices = defaultdict(list)
    for vertex, component in enumerate(membership):
        scc_to_vertices[component].append(vertex)

    communities = []
    for community in condensed_communities:
        vertices = set()
        for condensed_idx in community:
            scc_id = giant.vs[condensed_idx]["scc_id"]
            vertices.update(scc_to_vertices[scc_id])
        communities.append({names[v] for v in vertices})

    return communities


def graph_statistics(graph, scc):
    largest_scc_size = scc.giant().vcount()
    return {
        "nodes": graph.vcount(),
        "edges": graph.ecount(),
        "largest_scc_size": largest_scc_size,
    }


def analyze_graph(artifact_dir=ARTIFACT_DIR):
    src_arr, dst_arr, src_ids, dst_ids, names = load_edges(artifact_dir)
    n_vertices = len(names)

    report_print("Starting analysis...")

    graph = build_igraph(src_arr, dst_arr, n_vertices)

    del src_arr, dst_arr, src_ids, dst_ids
    gc.collect()

    scc = graph.connected_components(mode="strong")

    stats = graph_statistics(graph, scc)
    top_in_degree = top_degrees(graph, names, mode="in")
    top_out_degree = top_degrees(graph, names, mode="out")
    metadata = load_metadata(artifact_dir)

    communities = detect_communities(scc, names)

    del scc
    gc.collect()

    top_pagerank = pagerank_top_pages(graph, names)

    summaries = community_summary(communities, metadata)
    print_report(stats, communities, summaries, top_in_degree, top_out_degree, top_pagerank)

    return {
        "graph": graph,
        "communities": communities,
        "community_summaries": summaries,
        "stats": stats,
        "top_in_degree": top_in_degree,
        "top_out_degree": top_out_degree,
        "top_pagerank": top_pagerank,
    }


def load_metadata(artifact_dir=ARTIFACT_DIR):
    metadata = {}
    metadata_files = [f for f in os.listdir(artifact_dir) if f.endswith("_community.pkl")]
    for filename in metadata_files:
        path = os.path.join(artifact_dir, filename)
        with open(path, "rb") as f:
            metadata.update(pickle.load(f))
    return metadata


def community_summary(communities, metadata, top_n=10):
    summaries = []
    for community_id, nodes in enumerate(communities):
        counter = Counter()
        for node in nodes:
            data = metadata.get(node)
            if not data:
                continue
            counter.update(data["categories"])

        summaries.append({
            "community_id": community_id,
            "size": len(nodes),
            "top_categories": counter.most_common(10),
        })

    summaries.sort(key=lambda x: x["size"], reverse=True)
    return summaries[:top_n]


def print_report(stats, communities, summaries, top_in_degree, top_out_degree, top_pagerank):
    report_print("\n===== GRAPH ANALYSIS =====")

    report_print(f"Nodes: {stats['nodes']:,}")
    report_print(f"Edges: {stats['edges']:,}")
    report_print(f"Largest component: {stats['largest_scc_size']:,}")
    report_print(f"Detected communities: {len(communities):,}")

    report_print("\ntop in-degree")
    for title, degree in top_in_degree:
        report_print(f"{title[:60]:60} {degree:,}")

    report_print("\ntop out-degree")
    for title, degree in top_out_degree:
        report_print(f"{title[:60]:60} {degree:,}")

    report_print("\ntop pagerank")
    for title, score in top_pagerank:
        report_print(f"{title[:60]:60} {score:.6f}")

    for comm in summaries:
        report_print(f"\nCommunity {comm['community_id']}")
        report_print(f"Size: {comm['size']:,}")
        report_print("Top categories:")
        for cat, count in comm["top_categories"]:
            report_print(f"  - {cat}: {count}")