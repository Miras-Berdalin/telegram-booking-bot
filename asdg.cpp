#include <iostream>
#include <vector>
#include <algorithm>

using namespace std;

static const long long MOD = 1000000007;

struct Edge {
    int u, v, w;
};

struct DSU {
    vector<int> parent, sz;
    vector<long long> sum;

    DSU(int n) {
        parent.resize(n + 1);
        sz.assign(n + 1, 1);
        sum.resize(n + 1);
        for (int i = 1; i <= n; i++) {
            parent[i] = i;
            sum[i] = i;
        }
    }

    int find(int x) {
        if (parent[x] == x) return x;
        return parent[x] = find(parent[x]);
    }

    long long unite(int a, int b, int w) {
        a = find(a);
        b = find(b);
        if (a == b) return 0;
        long long res = (sum[a] * sum[b]) % MOD;
        if (sz[a] < sz[b]) swap(a, b);
        parent[b] = a;
        sz[a] += sz[b];
        sum[a] = (sum[a] + sum[b]) % MOD;
        return (res * w) % MOD;
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int N;
    cin >> N;

    vector<Edge> edges(N - 1);
    for (int i = 0; i < N - 1; i++) {
        cin >> edges[i].u >> edges[i].v >> edges[i].w;
    }

    sort(edges.begin(), edges.end(), [](const Edge &a, const Edge &b) {
        return a.w < b.w;
    });

    DSU dsu(N);
    long long ans = 0;

    for (int i = 0; i < N - 1; i++) {
        ans = (ans + dsu.unite(edges[i].u, edges[i].v, edges[i].w)) % MOD;
    }

    cout << ans << "\n";
    return 0;
}
