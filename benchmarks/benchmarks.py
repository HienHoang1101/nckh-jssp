"""
JSSP Benchmark instances and Best Known Solutions (BKS).

Includes:
- FT06 (Fisher & Thompson, 6x6, OPT=55)
- FT10 (Fisher & Thompson, 10x10, OPT=930)
- FT20 (Fisher & Thompson, 5x20, OPT=1165)
- LA01-LA40 (Lawrence 1984)
- TA01-TA50 (Taillard 1993) — selected subset

Data format: standard (machine duration) pairs per job.
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Optional
from algorithms.bnb.graph import JSSPInstance, parse_instance


# ============================================================================
# Best Known Solutions
# ============================================================================

BKS: dict[str, int] = {
    "FT06": 55,
    "FT10": 930,
    "FT20": 1165,
    "LA01": 666,
    "LA02": 655,
    "LA03": 597,
    "LA04": 590,
    "LA05": 593,
    "LA06": 926,
    "LA07": 890,
    "LA08": 863,
    "LA09": 951,
    "LA10": 958,
    "LA11": 1222,
    "LA12": 1039,
    "LA13": 1150,
    "LA14": 1292,
    "LA15": 1207,
    "LA16": 945,
    "LA17": 784,
    "LA18": 848,
    "LA19": 842,
    "LA20": 902,
    "LA21": 1046,
    "LA22": 927,
    "LA23": 1032,
    "LA24": 935,
    "LA25": 977,
    "LA26": 1218,
    "LA27": 1235,
    "LA28": 1216,
    "LA29": 1152,
    "LA30": 1355,
    "LA31": 1784,
    "LA32": 1850,
    "LA33": 1719,
    "LA34": 1721,
    "LA35": 1888,
    "LA36": 1268,
    "LA37": 1397,
    "LA38": 1196,
    "LA39": 1233,
    "LA40": 1222,
    "TA01": 1231,
    "TA02": 1244,
    "TA03": 1218,
    "TA04": 1175,
    "TA05": 1224,
    "TA06": 1238,
    "TA07": 1227,
    "TA08": 1217,
    "TA09": 1274,
    "TA10": 1241,
    "TA11": 1357,
    "TA12": 1367,
    "TA13": 1342,
    "TA14": 1345,
    "TA15": 1339,
    "TA16": 1360,
    "TA17": 1462,
    "TA18": 1396,
    "TA19": 1332,
    "TA20": 1348,
    "TA21": 1642,
    "TA22": 1600,
    "TA23": 1557,
    "TA24": 1644,
    "TA25": 1595,
    "TA26": 1643,
    "TA27": 1680,
    "TA28": 1603,
    "TA29": 1625,
    "TA30": 1584,
    "TA31": 1764,
    "TA32": 1774,
    "TA33": 1788,
    "TA34": 1828,
    "TA35": 2007,
    "TA36": 1819,
    "TA37": 1771,
    "TA38": 1673,
    "TA39": 1795,
    "TA40": 1669,
    "TA41": 2005,
    "TA42": 1937,
    "TA43": 1846,
    "TA44": 1979,
    "TA45": 2000,
    "TA46": 2004,
    "TA47": 1889,
    "TA48": 1943,
    "TA49": 1961,
    "TA50": 1923,
}

_BENCHMARKS_DIR = Path(__file__).resolve().parent
_BKS_JSON_FILE = _BENCHMARKS_DIR / "bks.json"


def _load_local_bks() -> dict[str, int]:
    """Load BKS values from the repository-local JSON file."""
    if not _BKS_JSON_FILE.exists():
        return {}

    try:
        payload = json.loads(_BKS_JSON_FILE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}

    local_bks: dict[str, int] = {}
    for instance_id, bks_value in payload.items():
        key = str(instance_id).strip().upper()
        if not key:
            continue
        try:
            local_bks[key] = int(bks_value)
        except (TypeError, ValueError):
            continue
    return local_bks

_EXTERNAL_BKS_FILE = Path(
    r"D:\thực nghiệm 3\_jssp_repo\data-raw\instances\instances_with_bks.txt"
)


def _load_external_bks() -> dict[str, int]:
    """Load BKS values from the external CSV catalog when available."""
    if not _EXTERNAL_BKS_FILE.exists():
        return {}

    external_bks: dict[str, int] = {}
    with _EXTERNAL_BKS_FILE.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            instance_id = (row.get("inst.id") or "").strip().upper()
            bks_value = (row.get("inst.bks") or "").strip()
            if not instance_id or not bks_value or bks_value == "NA":
                continue
            try:
                external_bks[instance_id] = int(bks_value)
            except ValueError:
                continue
    return external_bks


BKS.update(_load_local_bks())
BKS.update(_load_external_bks())


# ============================================================================
# Instance data — loaded from files in benchmarks/data/
# All instances are read from their respective data files at load time.
# ============================================================================

INSTANCES: dict[str, str] = {}

_DATA_DIR = _BENCHMARKS_DIR / "data"

_FISHER_DIRS = [
    _DATA_DIR / "fisher",
    Path(r"D:\thực nghiệm 3\JSSP_AI_RESEARCH\data\fisher"),
]
_LAWRENCE_DIRS = [
    _DATA_DIR / "lawrence",
    Path(r"D:\thực nghiệm 3\JSSP_AI_RESEARCH\data\lawrence"),
]
_TAILLARD_DIRS = [
    _DATA_DIR / "taillard",
    Path(r"D:\thực nghiệm 3\JSSP_AI_RESEARCH\data\taillard"),
]


_FISHER_DIRS = [_DATA_DIR / "fisher"]
_LAWRENCE_DIRS = [_DATA_DIR / "lawrence"]
_TAILLARD_DIRS = [_DATA_DIR / "taillard"]

def _load_instance_from_dirs(name: str, dirs: list[Path]) -> str | None:
    for directory in dirs:
        instance_file = directory / f"{name}.txt"
        if instance_file.exists():
            return instance_file.read_text(encoding="utf-8").strip()
    return None


def _iter_instance_names(dirs: list[Path], pattern: str):
    seen: set[str] = set()
    for directory in dirs:
        if not directory.exists():
            continue
        for instance_file in directory.glob(pattern):
            seen.add(instance_file.stem.upper())
    return seen


def _load_ft_instance_data(name: str) -> str | None:
    """Load FTxx instance text from benchmark folders."""
    if not name.startswith("FT"):
        return None
    return _load_instance_from_dirs(name, _FISHER_DIRS)


def _load_ta_instance_data(name: str) -> str | None:
    """Load TAxx instance text from local benchmark data folder."""
    if not name.startswith("TA"):
        return None
    return _load_instance_from_dirs(name, _TAILLARD_DIRS)


def _load_la_instance_data(name: str) -> str | None:
    """Load LAxx instance text from local benchmark data folder."""
    if not name.startswith("LA"):
        return None
    return _load_instance_from_dirs(name, _LAWRENCE_DIRS)


def load_instance(name: str) -> Optional[JSSPInstance]:
    """Load a benchmark instance by name."""
    name = name.upper()
    data = INSTANCES.get(name)
    if data is None:
        external_data = _load_ft_instance_data(name)
        if external_data is None:
            external_data = _load_ta_instance_data(name)
        if external_data is None:
            external_data = _load_la_instance_data(name)
        if external_data is None:
            return None
        INSTANCES[name] = external_data
        data = external_data
    bks = BKS.get(name)
    return parse_instance(name, data, bks)


def get_available_instances() -> list[str]:
    """Return list of available instance names."""
    names = set(INSTANCES.keys())
    names.update(_iter_instance_names(_FISHER_DIRS, "FT??.txt"))
    names.update(_iter_instance_names(_TAILLARD_DIRS, "TA??.txt"))
    names.update(_iter_instance_names(_LAWRENCE_DIRS, "LA??.txt"))
    return sorted(names)
