#!/usr/bin/env python3
"""
run_dp_batch.py — Chạy batch DP solver cho FT06, LA01-LA40, TA01-TA50.

Quy tắc:
  - Mỗi instance có giới hạn 3600 giây.
  - Nếu instance chạy quá 3600s (timeout) → KHÔNG ghi nhận kết quả.
  - Chỉ lưu các instance hoàn thành trong giới hạn thời gian.
  - Hỗ trợ checkpoint: resume nếu bị ngắt giữa chừng.

Sử dụng:
  cd jsp-project
  python scripts/run_dp_batch.py [--timeout 3600] [--output results/dp_batch.json]
  python scripts/run_dp_batch.py --resume   # tiếp tục từ checkpoint

Tham số:
  --timeout   INT     Giới hạn thời gian mỗi instance (mặc định 3600s)
  --output    PATH    File JSON lưu kết quả (mặc định results/dp_batch.json)
  --checkpoint PATH   File checkpoint (mặc định results/dp_batch_checkpoint.json)
  --resume            Tiếp tục từ checkpoint nếu có (mặc định True nếu checkpoint tồn tại)
  --fresh             Bỏ qua checkpoint, bắt đầu lại từ đầu
  --max-width INT     BDP beam width (0 = pure DP không giới hạn, mặc định 0)
  --log-level STR     DEBUG/INFO/WARNING (mặc định INFO)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Danh sách instances cần chạy
# ---------------------------------------------------------------------------
INSTANCES: list[str] = (
    ["FT06"]
    + [f"LA{i:02d}" for i in range(1, 41)]   # LA01..LA40
    + [f"TA{i:02d}" for i in range(1, 51)]   # TA01..TA50
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dp_batch")


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------
def run_instance(
    instance: str,
    timeout: int,
    max_width: int,
    project_root: Path,
) -> dict | None:
    """
    Chạy DP solver cho một instance qua subprocess.

    Trả về dict kết quả nếu hoàn thành trong timeout,
    hoặc None nếu timeout / lỗi (không ghi nhận).
    """
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, dir=project_root / "results"
    ) as tmp:
        tmp_path = tmp.name

    cmd = [
        sys.executable,
        str(project_root / "run.py"),
        "dp",
        instance,
        "--timeout", str(timeout),
        "--output", tmp_path,
        "--log-level", "WARNING",   # bớt log trong subprocess
    ]
    if max_width > 0:
        cmd += ["--max-width", str(max_width)]

    wall_limit = timeout + 60  # subprocess hard-kill sau solver_timeout + 60s buffer

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=wall_limit,
            cwd=str(project_root),
        )
        elapsed = time.perf_counter() - t0

        if proc.returncode != 0:
            err_lines = proc.stderr.decode(errors="replace").strip().splitlines()
            last_err = err_lines[-1] if err_lines else "unknown error"
            logger.warning("  [%s] subprocess lỗi: %s", instance, last_err)
            return None  # lỗi → không ghi nhận

        if not os.path.exists(tmp_path):
            logger.warning("  [%s] không tìm thấy file output", instance)
            return None

        with open(tmp_path, encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            return None

        result = data[0] if isinstance(data, list) else data

        # Nếu timeout → KHÔNG ghi nhận
        if result.get("timed_out", False):
            logger.info(
                "  [%s] TIMEOUT (%.1fs) → bỏ qua, không ghi nhận",
                instance, elapsed,
            )
            return None

        return result

    except subprocess.TimeoutExpired:
        logger.info(
            "  [%s] TIMEOUT (wall limit %ds) → bỏ qua, không ghi nhận",
            instance, wall_limit,
        )
        return None

    except Exception as exc:
        logger.warning("  [%s] ngoại lệ: %s", instance, exc)
        return None

    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------
def load_checkpoint(checkpoint_path: Path) -> dict:
    """Tải checkpoint. Trả về dict với 'done' (set), 'results' (list)."""
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, encoding="utf-8") as f:
                data = json.load(f)
            done = set(data.get("done", []))
            results = data.get("results", [])
            logger.info(
                "Checkpoint: đã hoàn thành %d/%d instances, có %d kết quả hợp lệ",
                len(done), len(INSTANCES), len(results),
            )
            return {"done": done, "results": results}
        except Exception as exc:
            logger.warning("Không đọc được checkpoint: %s — bắt đầu lại", exc)

    return {"done": set(), "results": []}


def save_checkpoint(
    checkpoint_path: Path,
    done: set[str],
    results: list[dict],
) -> None:
    """Lưu tiến trình hiện tại vào checkpoint."""
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "done": sorted(done),
        "results": results,
    }
    # Ghi vào file tạm rồi rename để tránh mất dữ liệu
    tmp = checkpoint_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    tmp.replace(checkpoint_path)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(results: list[dict], total: int, elapsed_total: float) -> None:
    n_opt = sum(1 for r in results if r.get("optimal_proven"))
    n_ok = len(results)
    n_skip = total - n_ok  # số instance timeout / lỗi / bị bỏ qua

    gaps = [
        r["gap_percent"] for r in results
        if r.get("gap_percent") is not None
    ]
    avg_gap = f"{sum(gaps)/len(gaps):.2f}" if gaps else "N/A"

    print(f"\n{'='*72}")
    print(f"  KẾT QUẢ DP BATCH")
    print(f"{'='*72}")
    print(
        f"  {'Instance':<12} {'Found':>8} {'BKS':>8} {'Gap%':>7} "
        f"{'Time(s)':>9} {'States':>12} {'Status':>10}"
    )
    print(f"  {'-'*70}")
    for r in results:
        status = "OPTIMAL" if r.get("optimal_proven") else "DONE"
        gap_s = "N/A" if r.get("gap_percent") is None else f"{r['gap_percent']:.2f}"
        found_s = str(r.get("best_makespan", "N/A"))
        bks_s = str(r.get("optimal_makespan", "N/A"))
        t_s = f"{r.get('computation_time_seconds', 0):.1f}"
        st_s = f"{r.get('states_explored', 0):,}"
        print(
            f"  {r.get('instance_name','?'):<12} {found_s:>8} {bks_s:>8} {gap_s:>7} "
            f"{t_s:>9} {st_s:>12} {status:>10}"
        )
    print(f"  {'-'*70}")
    print(f"  Tổng chạy:  {total} instances")
    print(f"  Ghi nhận:   {n_ok} instances (hoàn thành trong giới hạn)")
    print(f"  Bỏ qua:     {n_skip} instances (timeout / lỗi)")
    print(f"  Optimal:    {n_opt}/{n_ok}")
    print(f"  Gap TB:     {avg_gap}%")
    print(f"  Thời gian:  {str(timedelta(seconds=int(elapsed_total)))}")
    print(f"{'='*72}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch DP solver — FT06, LA01-LA40, TA01-TA50",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--timeout", type=int, default=3600,
                   help="Giới hạn thời gian mỗi instance (giây), mặc định 3600")
    p.add_argument("--output", default="results/dp_batch.json",
                   help="File JSON lưu kết quả cuối (mặc định results/dp_batch.json)")
    p.add_argument("--checkpoint", default="results/dp_batch_checkpoint.json",
                   help="File checkpoint để resume")
    p.add_argument("--fresh", action="store_true",
                   help="Bỏ qua checkpoint, chạy lại từ đầu")
    p.add_argument("--max-width", type=int, default=0,
                   help="BDP beam width (0 = pure DP, mặc định 0)")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    project_root = Path(__file__).resolve().parents[1]
    checkpoint_path = project_root / args.checkpoint
    output_path = project_root / args.output

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Tải hoặc khởi tạo checkpoint
    if args.fresh and checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("--fresh: đã xóa checkpoint cũ")

    state = load_checkpoint(checkpoint_path)
    done: set[str] = state["done"]
    results: list[dict] = state["results"]

    remaining = [inst for inst in INSTANCES if inst not in done]

    print(f"\n{'='*72}")
    print(f"  DP BATCH RUNNER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}")
    print(f"  Tổng instances:   {len(INSTANCES)}")
    print(f"  Đã hoàn thành:    {len(done)}")
    print(f"  Cần chạy:         {len(remaining)}")
    print(f"  Timeout/instance: {args.timeout}s")
    print(f"  BDP max-width:    {'unlimited (pure DP)' if args.max_width == 0 else args.max_width}")
    print(f"  Output:           {output_path}")
    print(f"  Checkpoint:       {checkpoint_path}")
    print(f"  Quy tắc:          Timeout → không ghi nhận kết quả")
    print(f"{'='*72}\n")

    if not remaining:
        print("Tất cả instances đã hoàn thành. Xuất kết quả cuối.")
    else:
        t_batch_start = time.perf_counter()
        for i, inst in enumerate(remaining, 1):
            eta_done = len(done)
            logger.info(
                "▶ [%d/%d] %s  (đã xong: %d, kết quả hợp lệ: %d) ...",
                i, len(remaining), inst, len(done), len(results),
            )
            t0 = time.perf_counter()
            result = run_instance(inst, args.timeout, args.max_width, project_root)
            elapsed = time.perf_counter() - t0

            if result is not None:
                results.append(result)
                status = "OPTIMAL" if result.get("optimal_proven") else "DONE"
                logger.info(
                    "  ✓ %s  makespan=%s  BKS=%s  gap=%s%%  time=%.1fs  [%s]",
                    inst,
                    result.get("best_makespan", "?"),
                    result.get("optimal_makespan", "?"),
                    result.get("gap_percent", "?"),
                    elapsed,
                    status,
                )
            else:
                logger.info(
                    "  ✗ %s  → timeout/lỗi, KHÔNG ghi nhận  (%.1fs)",
                    inst, elapsed,
                )

            done.add(inst)
            save_checkpoint(checkpoint_path, done, results)

            # Lưu kết quả trung gian sau mỗi instance thành công
            if results:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, default=str)

        elapsed_total = time.perf_counter() - t_batch_start
        print_summary(results, len(INSTANCES), elapsed_total)

    # Lưu kết quả cuối
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Đã lưu {len(results)} kết quả vào: {output_path}")

    # Xóa checkpoint khi hoàn thành toàn bộ
    if len(done) == len(INSTANCES):
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        logger.info("Đã xóa checkpoint (hoàn thành tất cả instances).")


if __name__ == "__main__":
    main()
