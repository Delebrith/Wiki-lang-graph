import networkx as nx


def degree_bipartite_layout(G, left_nodes, right_nodes):
    result = nx.bipartite_layout(G, left_nodes, aspect_ratio=1)

    degrees = sorted(list(set([val for (node, val) in G.degree()])), reverse=True)
    right_h_distance = 1 / len(degrees)

    for k in right_nodes:
        v = [result[k][0] + degrees.index(G.degree(k)) * right_h_distance, result[k][1]]
        result[k] = v

    return result
