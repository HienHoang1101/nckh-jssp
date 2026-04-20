#!/usr/bin/env python3
"""
jssp_tabu.py — i-STS (Iterated Simple Tabu Search)
====================================================
Cài đặt theo Watson et al. (2006)
"Deconstructing Nowicki & Smutnicki's i-TSAB"
Computers and Operations Research 33, 2623-2644

Cấu trúc thuật toán:
─────────────────────────────────────────────────────────────
PHASE 1 — INIT: Xây dựng Elite Set E (|E|=8)
  Với mỗi elite solution:
    s0 = random local optimum (steepest-descent từ random semi-active)
    e  = STS(s0, Xa iterations)   ← core tabu search
    Thêm e vào E nếu chưa có

PHASE 2 — PROPER WORK: Vòng lặp chính đến hết time / BKS
  Chọn alpha=e* (best), beta=ex (xa nhất trong E)
  phi = path_relink(e*, ex)      ← NIS path relinking
  ec  = STS(phi, Xb iterations)  ← intensification
  Thay ex trong E bằng ec
  Lặp lại

STS (Simple Tabu Search):
  - N5 neighborhood (Nowicki & Smutnicki 1996)
  - Tabu tenure: sample [TTmin,TTmax] mỗi TUI iterations
  - Aspiration: chấp nhận tabu move nếu beats global best
  - Trap detection: mobility check mỗi MTCI iterations
  - Trap escape: random walk theo N1

Tham số Watson et al. 2006:
  |E|   = 8
  Xa    = 20000 (15x15), 40000 (larger)
  Xb    = 4000  (15x15), 7000  (larger)
  TTmin = 5,  TTmax = 15   (tenure range)
  TUI   = 10               (tenure update interval)
  MTCI  = 100              (mobility trap check interval)
  Mthrs = 2                (mobility threshold)
  MWLnom= 5, MWLinc = 2   (walk length nominal & increment)
  pi=pd = 0.5              (intensification/diversification prob)

Usage:
    python jssp_tabu.py FT06.txt --timeout 3600 --verbose
    python jssp_tabu.py LA01.txt LA02.txt --timeout 3600 --output result.csv
    python jssp_tabu.py --all_la ../../benchmarks/data/lawrence \
        --timeout 3600 --output result.csv --verbose
"""
from __future__ import annotations
import argparse, csv, random, sys, time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

INF = 10**9

# ─────────────────────────────────────────────────────────────
# BKS
# ─────────────────────────────────────────────────────────────
BKS: Dict[str, int] = {
    "FT06": 55,   "FT10": 930,  "FT20": 1165,
    "LA01": 666,  "LA02": 655,  "LA03": 597,  "LA04": 590,  "LA05": 593,
    "LA06": 926,  "LA07": 890,  "LA08": 863,  "LA09": 951,  "LA10": 958,
    "LA11": 1222, "LA12": 1039, "LA13": 1150, "LA14": 1292, "LA15": 1207,
    "LA16": 945,  "LA17": 784,  "LA18": 848,  "LA19": 842,  "LA20": 902,
    "LA21": 1046, "LA22": 927,  "LA23": 1032, "LA24": 935,  "LA25": 977,
    "LA26": 1218, "LA27": 1235, "LA28": 1216, "LA29": 1152, "LA30": 1355,
    "LA31": 1784, "LA32": 1850, "LA33": 1719, "LA34": 1721, "LA35": 1888,
    "LA36": 1268, "LA37": 1397, "LA38": 1196, "LA39": 1233, "LA40": 1222,
}

# ─────────────────────────────────────────────────────────────
# 1. INSTANCE
# ─────────────────────────────────────────────────────────────
class Instance:
    """JSSP instance. op_id = job*nm + step."""
    __slots__ = ("name","nj","nm","n_ops","mach","dur","dur_flat","bks")
    def __init__(self, name, nj, nm, mach, dur):
        self.name     = name
        self.nj       = nj
        self.nm       = nm
        self.n_ops    = nj * nm
        self.mach     = mach      # mach[j][s] = machine
        self.dur      = dur       # dur[j][s]  = duration
        self.dur_flat = [dur[j][s] for j in range(nj) for s in range(nm)]
        self.bks      = BKS.get(name.upper(), -1)

def parse_instance(name: str, text: str) -> Instance:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    nj, nm = map(int, lines[0].split())
    mach, dur = [], []
    for j in range(nj):
        toks = list(map(int, lines[j+1].split()))
        mach.append([toks[2*k]   for k in range(nm)])
        dur.append( [toks[2*k+1] for k in range(nm)])
    return Instance(name, nj, nm, mach, dur)

# ─────────────────────────────────────────────────────────────
# 2. PARAMETERS (Watson et al. 2006, Table 1 + Section 5)
# ─────────────────────────────────────────────────────────────
class Params:
    """
    Tham số i-STS theo Watson et al. 2006.
    Điều chỉnh Xa/Xb theo kích thước instance.
    """
    ELITE_SIZE = 8          # |E| cố định = 8

    # Tabu tenure (STS): dynamic, sample [TTmin,TTmax] mỗi TUI iters
    TT_MIN = 5
    TT_MAX = 15
    TUI    = 10             # Tenure Update Interval

    # Trap detection (CMF framework)
    MTCI   = 100            # Mobility Trap Check Interval
    M_THRS = 2              # Mobility threshold
    MWL_NOM = 5             # Nominal walk length (N1 escape)
    MWL_INC = 2             # Walk length increment

    @staticmethod
    def get_Xa(nj: int, nm: int) -> int:
        """Số iterations cho STS trong INIT phase."""
        if nj <= 15 and nm <= 15:
            return 20_000
        return 40_000

    @staticmethod
    def get_Xb(nj: int, nm: int) -> int:
        """Số iterations cho STS trong PROPER WORK phase."""
        if nj <= 15 and nm <= 15:
            return 4_000
        return 7_000

# ─────────────────────────────────────────────────────────────
# 3. MAKESPAN — Topological Sort O(V+E)
# ─────────────────────────────────────────────────────────────
def _eval(inst: Instance, mo: List[List[int]]
          ) -> Tuple[int, List[int], List[int]]:
    """
    Tính (makespan, start[], tail[]) bằng topological sort.
    start[op] = thời điểm bắt đầu sớm nhất.
    tail[op]  = longest path từ cuối op đến makespan.
    Critical path: start[op] + dur[op] + tail[op] == makespan.
    """
    nj, nm = inst.nj, inst.nm
    n_ops  = inst.n_ops
    dur    = inst.dur_flat
    succ   = [[] for _ in range(n_ops)]
    indeg  = [0] * n_ops
    # Job-order edges
    for j in range(nj):
        for s in range(nm-1):
            u = j*nm+s; v = u+1
            succ[u].append(v); indeg[v] += 1
    # Machine-order edges
    for m in range(nm):
        seq = mo[m]
        for i in range(len(seq)-1):
            u, v = seq[i], seq[i+1]
            succ[u].append(v); indeg[v] += 1
    # Forward pass (Kahn + longest path)
    dist = [0]*n_ops
    q    = deque(op for op in range(n_ops) if indeg[op]==0)
    topo: List[int] = []
    while q:
        u = q.popleft(); topo.append(u)
        du = dist[u] + dur[u]
        for v in succ[u]:
            if du > dist[v]: dist[v] = du
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    if len(topo) != n_ops:
        dummy = [INF]*n_ops
        return INF, dummy, dummy
    makespan = max(dist[op]+dur[op] for op in range(n_ops))
    # Backward pass (tail)
    tail = [0]*n_ops
    for u in reversed(topo):
        best = 0
        for v in succ[u]:
            val = dur[v]+tail[v]
            if val > best: best = val
        tail[u] = best
    return makespan, dist, tail  # dist = start[]

def _ms(inst: Instance, mo: List[List[int]]) -> int:
    """Tính nhanh makespan (forward pass only, không cần tail)."""
    nj, nm = inst.nj, inst.nm
    n_ops  = inst.n_ops
    dur    = inst.dur_flat
    succ  = [[] for _ in range(n_ops)]
    indeg = [0]*n_ops
    for j in range(nj):
        for s in range(nm-1):
            u = j*nm+s; v = u+1
            succ[u].append(v); indeg[v] += 1
    for m in range(nm):
        seq = mo[m]
        for i in range(len(seq)-1):
            u, v = seq[i], seq[i+1]
            succ[u].append(v); indeg[v] += 1
    dist = [0]*n_ops
    q    = deque(op for op in range(n_ops) if indeg[op]==0)
    cnt  = 0
    while q:
        u = q.popleft(); cnt += 1
        du = dist[u]+dur[u]
        for v in succ[u]:
            if du > dist[v]: dist[v] = du
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    if cnt != n_ops: return INF
    return max(dist[op]+dur[op] for op in range(n_ops))

# ─────────────────────────────────────────────────────────────
# 4. N5 NEIGHBORHOOD (Nowicki & Smutnicki 1996)
# ─────────────────────────────────────────────────────────────
def _n5_neighbors(inst: Instance, mo: List[List[int]],
                   ms: int, start: List[int], tail: List[int]
                   ) -> List[Tuple[List[List[int]], Tuple[int,int,int]]]:
    """
    N5 neighborhood: với mỗi critical block B = [b1..bk] trên máy m:
      - Swap (b1, b2)      nếu k >= 2
      - Swap (b_{k-1}, bk) nếu k >= 2
      - Nếu k == 2: chỉ 1 swap (b1,b2) = (b_{k-1},bk)
    => O(#critical_blocks) moves, rất nhỏ.

    Watson et al. dùng đúng N5 này (không phải all-pairs).
    Tabu attribute: (min_op, max_op, machine)
    """
    dur    = inst.dur_flat
    result: List[Tuple[List[List[int]], Tuple[int,int,int]]] = []
    seen:   set = set()

    for m in range(inst.nm):
        seq = mo[m]; n = len(seq)
        if n < 2: continue
        # Đánh dấu op trên critical path
        on_cp = [start[op]+dur[op]+tail[op]==ms for op in seq]
        i = 0
        while i < n:
            if not on_cp[i]: i += 1; continue
            j = i
            while j < n and on_cp[j]: j += 1
            blen = j - i  # block length
            if blen >= 2:
                # Move 1: swap first pair in block (b1, b2)
                for (pi, pj) in [(i, i+1), (j-2, j-1)]:
                    if pi < 0 or pj >= n: continue
                    u, v = seq[pi], seq[pj]
                    attr = (min(u,v), max(u,v), m)
                    if attr in seen: continue
                    seen.add(attr)
                    ns2 = list(seq)
                    ns2[pi], ns2[pj] = ns2[pj], ns2[pi]
                    nmo = [list(s) for s in mo]
                    nmo[m] = ns2
                    result.append((nmo, attr))
            i = j
    return result

# ─────────────────────────────────────────────────────────────
# 5. N1 NEIGHBORHOOD (van Laarhoven 1992) — dùng cho trap escape
# ─────────────────────────────────────────────────────────────
def _n1_neighbors(inst: Instance, mo: List[List[int]],
                   ms: int, start: List[int], tail: List[int]
                   ) -> List[Tuple[List[List[int]], Tuple[int,int,int]]]:
    """
    N1: swap mọi cặp adjacent operations trong mọi critical block.
    Dùng cho random walk escape (N1 induces connected search space).
    """
    dur    = inst.dur_flat
    result = []
    seen: set = set()
    for m in range(inst.nm):
        seq = mo[m]; n = len(seq)
        if n < 2: continue
        on_cp = [start[op]+dur[op]+tail[op]==ms for op in seq]
        i = 0
        while i < n:
            if not on_cp[i]: i += 1; continue
            j = i
            while j < n and on_cp[j]: j += 1
            if j-i >= 2:
                for k in range(i, j-1):
                    u, v = seq[k], seq[k+1]
                    attr = (min(u,v), max(u,v), m)
                    if attr in seen: continue
                    seen.add(attr)
                    ns2 = list(seq)
                    ns2[k], ns2[k+1] = ns2[k+1], ns2[k]
                    nmo = [list(s) for s in mo]
                    nmo[m] = ns2
                    result.append((nmo, attr))
            i = j
    return result

# ─────────────────────────────────────────────────────────────
# 6. DISJUNCTIVE GRAPH DISTANCE (dùng cho path relinking)
# ─────────────────────────────────────────────────────────────
def _dg_distance(inst: Instance,
                  mo_a: List[List[int]],
                  mo_b: List[List[int]]) -> int:
    """
    Khoảng cách disjunctive graph giữa 2 nghiệm.
    = số cặp (op_i, op_j) có thứ tự khác nhau trên ít nhất 1 máy.
    Watson et al. dùng metric này để chọn Ex (xa nhất với E*).
    """
    dist = 0
    for m in range(inst.nm):
        seq_a = mo_a[m]; seq_b = mo_b[m]
        pos_a = {op: i for i, op in enumerate(seq_a)}
        pos_b = {op: i for i, op in enumerate(seq_b)}
        n = len(seq_a)
        for i in range(n):
            for j in range(i+1, n):
                u, v = seq_a[i], seq_a[j]
                if (pos_a[u] < pos_a[v]) != (pos_b[u] < pos_b[v]):
                    dist += 1
    return dist

# ─────────────────────────────────────────────────────────────
# 7. INITIAL SOLUTION — Semi-active schedule (Watson et al.)
# ─────────────────────────────────────────────────────────────
def _random_semi_active(inst: Instance) -> List[List[int]]:
    """
    Random semi-active schedule: Giffler-Thompson với alpha ngẫu nhiên.
    Watson et al. khởi tạo từ random semi-active, sau đó áp steepest descent.
    """
    nj, nm = inst.nj, inst.nm
    ns=[0]*nj; jr=[0]*nj; mr=[0]*nm
    mo: List[List[int]] = [[] for _ in range(nm)]
    while True:
        bf=INF; bm=-1
        for j in range(nj):
            s=ns[j]
            if s>=nm: continue
            m=inst.mach[j][s]; avail=max(jr[j],mr[m])
            f=avail+inst.dur[j][s]
            if f<bf or (f==bf and m<bm): bf,bm=f,m
        if bm<0: break
        conflict=[]
        for j in range(nj):
            s=ns[j]
            if s>=nm: continue
            m=inst.mach[j][s]
            if m!=bm: continue
            avail=max(jr[j],mr[m])
            if avail<bf: conflict.append((inst.dur[j][s],j,s,avail))
        if not conflict: break
        # Random selection from conflict set (semi-active)
        conflict.sort()
        alpha = random.uniform(0.0, 0.4)
        if alpha > 0 and len(conflict) > 1:
            thr = conflict[0][0]*(1.0+alpha)
            elig = [c for c in conflict if c[0]<=thr]
            _,j,s,avail = random.choice(elig)
        else:
            _,j,s,avail = conflict[0]
        op=j*nm+s
        mo[bm].append(op)
        fin=avail+inst.dur[j][s]
        jr[j]=fin; mr[bm]=fin; ns[j]+=1
    return mo

def _steepest_descent(inst: Instance, mo: List[List[int]],
                       deadline: float = float('inf')
                       ) -> Tuple[List[List[int]], int]:
    """
    Steepest descent đến local optimum (N5), có timeout.
    Dùng để lấy random local optimum từ semi-active schedule.
    """
    cur_mo = [list(s) for s in mo]
    ms, start, tail = _eval(inst, cur_mo)
    improved = True
    while improved:
        if time.time() > deadline: break   # timeout guard
        improved = False
        nbrs = _n5_neighbors(inst, cur_mo, ms, start, tail)
        for (nmo, attr) in nbrs:
            nms = _ms(inst, nmo)
            if nms < ms:
                cur_mo = nmo; ms = nms
                ms2, start, tail = _eval(inst, cur_mo)
                ms = ms2
                improved = True
                break
    return cur_mo, ms

def _random_local_optimum(inst: Instance,
                            deadline: float = float('inf')
                            ) -> Tuple[List[List[int]], int]:
    """
    Tạo random local optimum: semi-active → steepest descent.
    Watson et al. Section 3.2: "search begins from a random local optimum".
    """
    mo = _random_semi_active(inst)
    return _steepest_descent(inst, mo, deadline=deadline)

# ─────────────────────────────────────────────────────────────
# 8. CMF — Core Metaheuristic Framework (Watson et al. Fig. 1)
# ─────────────────────────────────────────────────────────────
def _random_walk_n1(inst: Instance, mo: List[List[int]],
                     walk_len: int) -> Tuple[List[List[int]], int]:
    """
    Random walk theo N1 để escape trap.
    Chọn random neighbor theo N1 tại mỗi bước.
    """
    cur_mo = [list(s) for s in mo]
    ms, start, tail = _eval(inst, cur_mo)
    for _ in range(walk_len):
        nbrs = _n1_neighbors(inst, cur_mo, ms, start, tail)
        if not nbrs:
            # Không có N1 neighbors: thêm random swap bất kỳ
            m = random.randrange(inst.nm)
            seq = cur_mo[m]
            if len(seq) >= 2:
                i, j = random.sample(range(len(seq)), 2)
                new_seq = list(seq)
                new_seq[i], new_seq[j] = new_seq[j], new_seq[i]
                new_mo = [list(s) for s in cur_mo]
                new_mo[m] = new_seq
                cur_mo = new_mo
            break
        nmo, _ = random.choice(nbrs)
        cur_mo = nmo
        ms2, start, tail = _eval(inst, cur_mo)
        ms = ms2
    return cur_mo, ms

# ─────────────────────────────────────────────────────────────
# 9. STS — Simple Tabu Search (Watson et al. Section 3.4)
# ─────────────────────────────────────────────────────────────
def _sts(inst: Instance,
          init_mo: List[List[int]],
          max_iters: int,
          g_best_ms: int,
          time_limit_abs: float,
          verbose: bool = False,
          label: str = ""
          ) -> Tuple[List[List[int]], int]:
    """
    Simple Tabu Search (STS) — Watson et al. Section 3.4:
    - N5 neighborhood
    - Dynamic tabu tenure: sample [TTmin,TTmax] mỗi TUI iterations
    - Aspiration criterion
    - CMF trap detection (mobility check mỗi MTCI iterations)
    - Trap escape: random walk theo N1

    Trả về (best_mo, best_ms) sau max_iters iterations hoặc hết time.
    """
    p = Params
    cur_mo = [list(s) for s in init_mo]
    ms, start, tail = _eval(inst, cur_mo)
    cur_ms = ms

    best_mo = [list(s) for s in cur_mo]
    best_ms = cur_ms

    # Tabu list: attr -> expiry iteration
    tabu: Dict[Tuple[int,int,int], int] = {}
    # Initial tenure
    tt_cur = random.randint(p.TT_MIN, p.TT_MAX)

    # CMF state
    last_mtci_mo = [list(s) for s in cur_mo]
    verify_trap_escape = False
    mwl_cur = 0

    for itr in range(1, max_iters+1):
        if time.time() > time_limit_abs: break
        if inst.bks > 0 and best_ms <= inst.bks: break

        # ── Trap detection (CMF) ──────────────────────────────
        generate_trap_escape = False
        if itr % p.MTCI == 0:
            if time.time() > time_limit_abs: break
            mob = _dg_distance(inst, cur_mo, last_mtci_mo)
            if verify_trap_escape and mob > p.M_THRS:
                verify_trap_escape = False
            elif verify_trap_escape and mob <= p.M_THRS:
                mwl_cur += p.MWL_INC
                generate_trap_escape = True
            elif not verify_trap_escape and mob <= p.M_THRS:
                mwl_cur = p.MWL_NOM
                generate_trap_escape = True
                verify_trap_escape = True
            last_mtci_mo = [list(s) for s in cur_mo]

        if generate_trap_escape:
            # Escape trap: random walk theo N1
            cur_mo, ms2 = _random_walk_n1(inst, cur_mo, int(mwl_cur))
            ms2_r, start, tail = _eval(inst, cur_mo)
            cur_ms = ms2_r
            continue

        # ── Tenure update (TUI) ───────────────────────────────
        if itr % p.TUI == 0:
            tt_cur = random.randint(p.TT_MIN, p.TT_MAX)

        # ── Generate N5 neighbors ─────────────────────────────
        nbrs = _n5_neighbors(inst, cur_mo, cur_ms, start, tail)

        if not nbrs:
            # Không có N5 neighbor → small N1 perturbation
            cur_mo, ms_r = _random_walk_n1(inst, cur_mo, p.MWL_NOM)
            ms2_r, start, tail = _eval(inst, cur_mo)
            cur_ms = ms2_r
            continue

        # ── Select best admissible move ───────────────────────
        adm_ms=INF; adm_mo=None; adm_attr=None
        asp_ms=INF; asp_mo=None; asp_attr=None
        all_ms=INF; all_mo=None; all_attr=None

        for (nmo, attr) in nbrs:
            nms = _ms(inst, nmo)
            if nms < all_ms: all_ms,all_mo,all_attr=nms,nmo,attr
            if tabu.get(attr,0) > itr:
                if nms < g_best_ms and nms < asp_ms:
                    asp_ms,asp_mo,asp_attr=nms,nmo,attr
            else:
                if nms < adm_ms:
                    adm_ms,adm_mo,adm_attr=nms,nmo,attr

        if asp_mo is not None and asp_ms < adm_ms:
            ch_ms,ch_mo,ch_attr=asp_ms,asp_mo,asp_attr
        elif adm_mo is not None:
            ch_ms,ch_mo,ch_attr=adm_ms,adm_mo,adm_attr
        elif asp_mo is not None:
            ch_ms,ch_mo,ch_attr=asp_ms,asp_mo,asp_attr
        else:
            ch_ms,ch_mo,ch_attr=all_ms,all_mo,all_attr
            if ch_mo is None: break

        # ── Apply move ────────────────────────────────────────
        cur_mo = ch_mo
        ms2, start, tail = _eval(inst, cur_mo)
        cur_ms = ms2

        # Add to tabu (symmetric)
        tabu[ch_attr] = itr + tt_cur
        u2,v2,m2 = ch_attr; tabu[(v2,u2,m2)] = itr + tt_cur

        if cur_ms < best_ms:
            best_ms = cur_ms
            best_mo = [list(s) for s in cur_mo]
            if verbose:
                el = time.time() - _T0
                print(f"  {label}[itr={itr:6d} t={el:.1f}s] "
                      f"New best: {best_ms}", flush=True)
        if cur_ms < g_best_ms: g_best_ms = cur_ms

        # Cleanup tabu
        if itr % 2000 == 0:
            tabu = {k:v for k,v in tabu.items() if v > itr}

    return best_mo, best_ms

_T0 = time.time()

# ─────────────────────────────────────────────────────────────
# 10. PATH RELINKING — NIS (Watson et al. Section 5)
# ─────────────────────────────────────────────────────────────
def _nis_path_relink(inst: Instance,
                      e_star: List[List[int]],
                      e_x: List[List[int]],
                      max_v: float = 0.5
                      ) -> List[List[int]]:
    """
    NIS Path Relinking: tạo solution phi "roughly equi-distant" từ e* và ex.
    Watson et al. dùng maxV=0.5.

    Implementation: tạo interpolation bằng cách blend machine orders.
    Với mỗi máy m, chọn ngẫu nhiên một số positions từ e_x để
    insert vào e_star, tạo ra intermediate solution.
    """
    nj, nm = inst.nj, inst.nm
    new_mo = [list(s) for s in e_star]

    dist = _dg_distance(inst, e_star, e_x)
    target = int(dist * max_v)  # đi max_v% quãng đường từ e* đến ex

    # Apply target random swaps hướng về ex
    steps = 0
    for m in range(nm):
        if steps >= target: break
        seq_star = list(new_mo[m])
        seq_x    = e_x[m]
        pos_star = {op: i for i, op in enumerate(seq_star)}
        # Tìm các vị trí khác nhau
        diffs = []
        for i in range(len(seq_x)):
            if seq_x[i] != seq_star[pos_star[seq_x[i]]]:
                diffs.append(i)
        for d in diffs:
            if steps >= target: break
            op_x = seq_x[d]
            pi   = pos_star[op_x]
            if pi != d:
                # Swap op_x về vị trí d
                op_at_d = seq_star[d]
                seq_star[d], seq_star[pi] = seq_star[pi], seq_star[d]
                pos_star[op_x] = d; pos_star[op_at_d] = pi
                steps += 1
        new_mo[m] = seq_star

    return new_mo

# ─────────────────────────────────────────────────────────────
# 11. i-STS MAIN ALGORITHM (Watson et al. 2006)
# ─────────────────────────────────────────────────────────────
def solve(inst: Instance,
          time_limit: float = 3600.0,
          verbose: bool = False,
          seed: Optional[int] = None
          ) -> Tuple[int, float]:
    """
    i-STS (Iterated Simple Tabu Search) — Watson et al. 2006.

    PHASE 1 — INIT:
      Xây dựng Elite Set E với |E|=ELITE_SIZE solutions
      Mỗi solution: random local optimum → STS(Xa iters)

    PHASE 2 — PROPER WORK (lặp đến hết time hoặc đạt BKS):
      e*  = argmin makespan trong E
      ex  = solution xa nhất với e* (disjunctive graph distance)
      phi = NIS_path_relink(e*, ex)
      ec  = STS(phi, Xb iters)
      Thay ex trong E bằng ec
    """
    global _T0
    if seed is not None: random.seed(seed)
    _T0 = time.time()
    t0  = _T0
    rem = lambda: time_limit - (time.time()-t0)
    el  = lambda: time.time()-t0

    Xa = Params.get_Xa(inst.nj, inst.nm)
    Xb = Params.get_Xb(inst.nj, inst.nm)
    E_SIZE = Params.ELITE_SIZE
    bks    = inst.bks

    if verbose:
        print(f"  [i-STS] Xa={Xa} Xb={Xb} |E|={E_SIZE} "
              f"TTmin={Params.TT_MIN} TTmax={Params.TT_MAX} "
              f"TUI={Params.TUI}", flush=True)

    # ── PHASE 1: Build Elite Set ──────────────────────────────
    E: List[List[List[int]]] = []      # elite solutions (machine orders)
    E_ms: List[int] = []               # makespans
    g_best_ms = INF
    g_best_mo = None

    if verbose:
        print(f"  [INIT] Building elite set |E|={E_SIZE} ...", flush=True)

    for e_idx in range(E_SIZE):
        if rem() < 1: break
        if bks > 0 and g_best_ms <= bks: break

        # Random local optimum (với deadline để không vượt timeout)
        s0_mo, s0_ms = _random_local_optimum(inst, deadline=t0+time_limit)

        # STS từ s0
        lbl = f"INIT e{e_idx+1}/{E_SIZE} "
        e_mo, e_ms = _sts(inst, s0_mo, Xa, g_best_ms,
                          t0+time_limit, verbose, lbl)

        # Cập nhật global best
        if e_ms < g_best_ms:
            g_best_ms = e_ms
            g_best_mo = [list(s) for s in e_mo]

        # Thêm vào E (không trùng makespan — đơn giản hóa)
        is_dup = any(abs(e_ms - em) == 0 and e_mo == E[i]
                     for i, em in enumerate(E_ms))
        if not is_dup:
            E.append([list(s) for s in e_mo])
            E_ms.append(e_ms)
        else:
            # Nếu trùng, vẫn thêm nhưng với small perturbation
            E.append([list(s) for s in e_mo])
            E_ms.append(e_ms)

    if not E:
        mo, ms = _random_local_optimum(inst)
        E = [[list(s) for s in mo]]; E_ms = [ms]
        g_best_ms = ms; g_best_mo = [list(s) for s in mo]

    if verbose:
        print(f"  [INIT] Done. Best={g_best_ms} "
              f"(t={el():.1f}s)", flush=True)

    # Early stop nếu INIT đã đạt BKS
    if bks > 0 and g_best_ms <= bks:
        if verbose: print(f"  BKS {bks} reached at INIT!", flush=True)
        return g_best_ms, el()

    # ── PHASE 2: Proper Work ──────────────────────────────────
    pw_itr = 0
    if verbose:
        print(f"  [PROPER WORK] Starting ...", flush=True)

    while rem() > 0.5:
        if bks > 0 and g_best_ms <= bks:
            if verbose: print(f"  BKS {bks} reached!", flush=True)
            break

        pw_itr += 1

        # e* = best solution in E
        star_idx = min(range(len(E)), key=lambda i: E_ms[i])
        e_star = E[star_idx]; e_star_ms = E_ms[star_idx]

        # ex = solution farthest from e* in E
        dists = [_dg_distance(inst, e_star, E[i])
                 if i != star_idx else -1
                 for i in range(len(E))]
        x_idx = max(range(len(E)), key=lambda i: dists[i])
        e_x   = E[x_idx]

        # Nếu khoảng cách quá nhỏ → chọn random
        if dists[x_idx] <= 0:
            x_idx = random.randrange(len(E))
            e_x   = E[x_idx]

        # NIS path relinking giữa e* và ex
        phi = _nis_path_relink(inst, e_star, e_x, max_v=0.5)

        # STS từ phi
        lbl = f"PW#{pw_itr} "
        ec_mo, ec_ms = _sts(inst, phi, Xb, g_best_ms,
                             t0+time_limit, verbose, lbl)

        # Cập nhật global best
        if ec_ms < g_best_ms:
            g_best_ms = ec_ms
            g_best_mo = [list(s) for s in ec_mo]

        # Thay ex trong E bằng ec (unconditional replacement)
        E[x_idx]    = [list(s) for s in ec_mo]
        E_ms[x_idx] = ec_ms

    return g_best_ms, el()

# ─────────────────────────────────────────────────────────────
# 12. CLI & RUNNER
# ─────────────────────────────────────────────────────────────
def _run_one(path: Path, timeout: float, n_runs: int,
             verbose: bool, seed: Optional[int]) -> dict:
    """
    Chạy n_runs lần độc lập cho 1 instance.
    Ghi nhận: best makespan, avg makespan, worst makespan,
              RE(%) của best, tổng thời gian chạy.
    """
    text = path.read_text(encoding="utf-8")
    name = path.stem.upper()
    inst = parse_instance(name, text)
    size = f"{inst.nj}x{inst.nm}"
    bks  = BKS.get(name, -1)
    Xa   = Params.get_Xa(inst.nj, inst.nm)
    Xb   = Params.get_Xb(inst.nj, inst.nm)

    print(f"\n{'='*70}", flush=True)
    print(f"  Instance : {name}  ({size})  BKS={bks}  "
          f"timeout={timeout}s/run  runs={n_runs}", flush=True)
    print(f"  Algorithm: i-STS (Watson et al. 2006)", flush=True)
    print(f"  Params   : |E|={Params.ELITE_SIZE}  Xa={Xa}  Xb={Xb}  "
          f"TTmin={Params.TT_MIN}  TTmax={Params.TT_MAX}  "
          f"TUI={Params.TUI}  MTCI={Params.MTCI}", flush=True)
    print(f"  {'Run':<5} {'Makespan':>10} {'RE(%)':>8} {'Time(s)':>9} {'Status':<6}",
          flush=True)
    print(f"  {'-'*46}", flush=True)

    makespans: List[int]   = []
    times:     List[float] = []

    for run_i in range(1, n_runs + 1):
        # Seed khác nhau cho mỗi lần chạy để đảm bảo độc lập
        run_seed = (seed + run_i) if seed is not None else None

        # Mỗi run có deadline riêng = thời điểm hiện tại + timeout
        run_start = time.time()
        ms, et = solve(inst, time_limit=timeout,
                       verbose=False, seed=run_seed)
        # Đảm bảo et không vượt timeout (safety cap)
        et = min(et, time.time() - run_start)
        makespans.append(ms)
        times.append(et)

        re_i = (ms - bks) / bks * 100.0 if bks > 0 else float("nan")
        st_i = "OPT" if ms == bks else ("NEAR" if re_i < 2.0 else "FAR")
        mrk  = "+" if st_i=="OPT" else ("~" if st_i=="NEAR" else "x")

        print(f"  {mrk} {run_i:<4d} {ms:>10d} {re_i:>7.2f}% "
              f"{et:>8.2f}s  {st_i}", flush=True)

    # Thống kê tổng hợp
    best_ms  = min(makespans)
    worst_ms = max(makespans)
    avg_ms   = sum(makespans) / len(makespans)
    total_t  = sum(times)
    avg_t    = total_t / len(times)

    re_best  = (best_ms  - bks) / bks * 100.0 if bks > 0 else float("nan")
    re_avg   = (avg_ms   - bks) / bks * 100.0 if bks > 0 else float("nan")
    re_worst = (worst_ms - bks) / bks * 100.0 if bks > 0 else float("nan")

    n_opt  = sum(1 for ms in makespans if ms == bks)
    status = "OPT" if best_ms == bks else ("NEAR" if re_best < 2.0 else "FAR")

    print(f"  {'-'*46}", flush=True)
    print(f"  Best  : {best_ms}   RE={re_best:.2f}%", flush=True)
    print(f"  Avg   : {avg_ms:.1f}  RE={re_avg:.2f}%", flush=True)
    print(f"  Worst : {worst_ms}   RE={re_worst:.2f}%", flush=True)
    print(f"  OPT   : {n_opt}/{n_runs} lần  |  Avg time: {avg_t:.2f}s",
          flush=True)

    return {
        "Instance":         name,
        "Kích thước":       size,
        "BKS":              bks,
        "Makespan (Best)":  best_ms,
        "Makespan (Avg)":   f"{avg_ms:.2f}",
        "Makespan (Worst)": worst_ms,
        "RE_best (%)":      f"{re_best:.4f}",
        "RE_avg (%)":       f"{re_avg:.4f}",
        "RE_worst (%)":     f"{re_worst:.4f}",
        "Time_avg (s)":     f"{avg_t:.2f}",
        "Time_total (s)":   f"{total_t:.2f}",
        "OPT/Runs":         f"{n_opt}/{n_runs}",
        "Status":           status,
    }

def main():
    ap = argparse.ArgumentParser(
        description="i-STS — Watson et al. (2006) JSSP Tabu Search")
    ap.add_argument("instances", nargs="*",
                    help="Path(s) to .txt instance files")
    ap.add_argument("--all_la", type=Path, default=None,
                    help="Folder containing LA01.txt..LA40.txt")
    ap.add_argument("--timeout", "-t", type=float, default=3600.0,
                    help="Time limit per instance per run (s). Default=3600")
    ap.add_argument("--runs", "-r", type=int, default=30,
                    help="Number of independent runs per instance. Default=30")
    ap.add_argument("--output", "-o", type=Path, default=None,
                    help="CSV output file path")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Print each improvement within a run")
    ap.add_argument("--seed", type=int, default=None,
                    help="Base random seed (each run uses seed+run_index)")
    args = ap.parse_args()

    # Thu thập danh sách file
    paths: List[Path] = []
    if args.all_la:
        d = args.all_la
        if not d.is_dir():
            print(f"ERROR: '{d}' is not a directory"); sys.exit(1)
        for i in range(1, 41):
            f = d / f"LA{i:02d}.txt"
            if f.exists(): paths.append(f)
            else: print(f"  WARN: {f} not found")
        if not paths:
            print(f"ERROR: no LA files in {d}"); sys.exit(1)
    for s in args.instances:
        f = Path(s)
        if not f.exists():
            print(f"ERROR: '{f}' not found"); sys.exit(1)
        paths.append(f)
    if not paths:
        ap.print_help(); sys.exit(1)

    FIELDNAMES = [
        "Instance", "Kích thước", "BKS",
        "Makespan (Best)", "Makespan (Avg)", "Makespan (Worst)",
        "RE_best (%)", "RE_avg (%)", "RE_worst (%)",
        "Time_avg (s)", "Time_total (s)",
        "OPT/Runs", "Status",
    ]

    print(f"\n  i-STS Tabu Search — Watson et al. (2006)", flush=True)
    print(f"  Instances: {len(paths)}  |  Runs/instance: {args.runs}  "
          f"|  Timeout/run: {args.timeout}s", flush=True)

    # Khởi tạo CSV ngay từ đầu — ghi header nếu file chưa tồn tại
    csv_fh = None
    csv_wr = None
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        file_exists = args.output.exists()
        csv_fh = open(args.output, "a", newline="", encoding="utf-8-sig")
        csv_wr = csv.DictWriter(csv_fh, fieldnames=FIELDNAMES, delimiter=";")
        if not file_exists:
            csv_wr.writeheader()
            csv_fh.flush()
        mode = "append (tiếp tục)" if file_exists else "tạo mới"
        print(f"  CSV : {args.output}  [{mode}]", flush=True)

    # Chạy từng instance, ghi CSV ngay sau khi xong
    rows = []
    for path in paths:
        row = _run_one(path, args.timeout, args.runs,
                       args.verbose, args.seed)
        rows.append(row)

        # Ghi ngay vào CSV — không chờ đến cuối
        if csv_wr is not None:
            csv_wr.writerow(row)
            csv_fh.flush()
            print(f"  [CSV] Da ghi {row['Instance']} -> {args.output}", flush=True)

    if csv_fh is not None:
        csv_fh.close()
        print(f"\n  CSV hoan tat -> {args.output}", flush=True)

    # In tổng kết
    if rows:
        n_opt  = sum(1 for r in rows if r["Status"] == "OPT")
        n_near = sum(1 for r in rows if r["Status"] == "NEAR")
        n_far  = sum(1 for r in rows if r["Status"] == "FAR")
        total  = len(rows)

        re_best_vals = [float(r["RE_best (%)"])
                        for r in rows if str(r["BKS"]) != "-1"]
        re_avg_vals  = [float(r["RE_avg (%)"])
                        for r in rows if str(r["BKS"]) != "-1"]

        print(f"\n{'='*70}", flush=True)
        print(f"{'TỔNG KẾT':^70}", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"  Tổng instances  : {total}", flush=True)
        print(f"  Số lần chạy/inst: {args.runs}", flush=True)
        print(f"  OPT  (RE=0.00%) : {n_opt:3d}/{total}", flush=True)
        print(f"  NEAR (RE<2.00%) : {n_near:3d}/{total}", flush=True)
        print(f"  FAR  (RE>=2.00%): {n_far:3d}/{total}", flush=True)
        if re_best_vals:
            print(f"  Avg RE (best)   : "
                  f"{sum(re_best_vals)/len(re_best_vals):.3f}%", flush=True)
            print(f"  Avg RE (avg)    : "
                  f"{sum(re_avg_vals)/len(re_avg_vals):.3f}%", flush=True)
            print(f"  Max RE (best)   : {max(re_best_vals):.3f}%", flush=True)

        print(f"\n  {'Instance':<10} {'Size':<8} {'BKS':>6} "
              f"{'Best':>6} {'Avg':>8} {'Worst':>6} "
              f"{'RE_best':>8} {'RE_avg':>8} {'OPT/N':>6} Status",
              flush=True)
        print(f"  {'-'*78}", flush=True)
        for r in rows:
            mrk = "+" if r["Status"]=="OPT" else \
                  ("~" if r["Status"]=="NEAR" else "x")
            print(f"  {mrk} {r['Instance']:<9} {r['Kích thước']:<8} "
                  f"{r['BKS']:>6} "
                  f"{r['Makespan (Best)']:>6} "
                  f"{float(r['Makespan (Avg)']):>8.1f} "
                  f"{r['Makespan (Worst)']:>6} "
                  f"{float(r['RE_best (%)']):>7.2f}% "
                  f"{float(r['RE_avg (%)']):>7.2f}% "
                  f"{r['OPT/Runs']:>6}  {r['Status']}",
                  flush=True)
        print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    main()