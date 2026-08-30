"""
Runs the REAL LLM diagnostician (call_llm_diagnostician, via a live
Groq call) against the same 50-case golden set the stub is measured
on, and reports both side by side -- per-class, not just one blended
number, same discipline as tests/test_golden_set_diagnosis.py and
scripts/calibration_report.py.

THIS SCRIPT MAKES REAL NETWORK CALLS AND COSTS REAL MONEY (a very
small amount -- 50 short classification calls on a cheap model). It is
the ONLY place in this codebase that does. Everything else -- the
batch runner, the ablation arms, the red-team suite, the calibration
report against the stub -- remains free and reproducible without any
key, exactly as before. Running this script does not change that.

TAKES ~7-8 MINUTES on Groq's free tier: paced with a delay between
calls (see DEFAULT_DELAY_SECONDS) to stay under the 8,000 tokens/min
limit, with automatic retry-with-backoff if a rate limit is still hit.
Use --delay to go faster on a paid tier with a higher limit.

Requires:
  pip install openai
  GROQ_API_KEY set (in your environment or a loaded .env file)
Optional:
  LLM_MODEL to override the default (openai/gpt-oss-20b)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from app.agents.diagnostician import call_llm_diagnostician, DiagnosticInput, TEACHER_STUB
from app.agents.llm_client import LLMClient, LLMClientError, ChatResponse

GOLDEN_SET_PATH = Path(__file__).resolve().parents[1] / "tests" / "golden_set" / "diagnosis_golden_set.json"

DEFAULT_DELAY_SECONDS = 9.0
MAX_RETRIES_ON_RATE_LIMIT = 5


def _load_golden_set() -> list[dict]:
    with open(GOLDEN_SET_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def _build_real_client() -> LLMClient:
    try:
        from openai import OpenAI, RateLimitError
    except ImportError:
        print("ERROR: the `openai` package is required for a live comparison.")
        print("Install it with: pip install openai")
        sys.exit(1)

    class OpenAICompatibleTransport:
        def chat_completion(self, base_url, api_key, model, system, user, response_format_json):
            client = OpenAI(base_url=base_url, api_key=api_key)
            last_error = None
            for attempt in range(MAX_RETRIES_ON_RATE_LIMIT):
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        response_format={"type": "json_object"} if response_format_json else None,
                    )
                    return ChatResponse(status_code=200, json_body=resp.model_dump())
                except RateLimitError as e:
                    last_error = e
                    wait = min(2 ** attempt * 2, 30)
                    print(f"    rate limited -- waiting {wait}s before retry "
                          f"{attempt + 1}/{MAX_RETRIES_ON_RATE_LIMIT}...")
                    time.sleep(wait)
            raise last_error

    client = LLMClient(transport=OpenAICompatibleTransport())
    if not client.api_key:
        print("ERROR: GROQ_API_KEY is not set. Set it in your environment or a loaded .env file.")
        sys.exit(1)
    return client


def run_comparison(delay_seconds: float = DEFAULT_DELAY_SECONDS) -> dict:
    golden = _load_golden_set()
    client = _build_real_client()

    stub_correct = 0
    llm_correct = 0
    llm_errors = 0
    per_class_llm = defaultdict(lambda: {"tp": 0, "support": 0})
    rows = []

    for i, entry in enumerate(golden, start=1):
        inp = DiagnosticInput(
            case_id=entry["id"], error_code=entry["error_code"], error_reason=entry.get("error_reason"),
            error_source=entry["error_source"],
            error_step=entry["error_step"], error_description=entry["error_description"], prior_failures=0,
        )
        true_cause = entry["true_root_cause"]

        stub_result = TEACHER_STUB(inp)
        stub_ok = stub_result.root_cause == true_cause
        if stub_ok:
            stub_correct += 1

        try:
            llm_result = call_llm_diagnostician(inp, client)
            llm_ok = llm_result.root_cause == true_cause
            llm_pred = llm_result.root_cause
            llm_conf = llm_result.confidence
            if llm_ok:
                llm_correct += 1
            per_class_llm[true_cause]["support"] += 1
            if llm_ok:
                per_class_llm[true_cause]["tp"] += 1
        except LLMClientError as e:
            llm_errors += 1
            llm_ok = False
            llm_pred = f"ERROR: {e}"
            llm_conf = None

        rows.append({
            "id": entry["id"], "true": true_cause,
            "stub_pred": stub_result.root_cause, "stub_ok": stub_ok,
            "llm_pred": llm_pred, "llm_ok": llm_ok, "llm_conf": llm_conf,
        })
        print(f"[{i}/{len(golden)}] {entry['id']}: true={true_cause} "
              f"stub={'OK' if stub_ok else 'MISS'} llm={'OK' if llm_ok else 'MISS'}")

        if i < len(golden):
            time.sleep(delay_seconds)

    return {
        "n": len(golden), "stub_correct": stub_correct, "llm_correct": llm_correct,
        "llm_errors": llm_errors, "per_class_llm": dict(per_class_llm), "rows": rows,
        "model": client.model,
    }


def print_report(result: dict) -> None:
    n = result["n"]
    print(f"\n{'=' * 60}")
    print(f"Golden-set comparison: stub vs live {result['model']} (n={n})\n")
    print(f"  stub accuracy:  {result['stub_correct']}/{n} = {result['stub_correct']/n:.1%}")
    print(f"  LLM accuracy:   {result['llm_correct']}/{n} = {result['llm_correct']/n:.1%}")
    if result["llm_errors"]:
        print(f"  LLM API errors: {result['llm_errors']} (counted as misses above)")

    print("\nPer-class LLM recall:")
    for cause, d in sorted(result["per_class_llm"].items()):
        recall = d["tp"] / d["support"] if d["support"] else 0.0
        print(f"  {cause:22s} {d['tp']:2d}/{d['support']:2d} = {recall:.1%}")

    misses = [r for r in result["rows"] if not r["llm_ok"]]
    if misses:
        print("\nLLM misses (true -> predicted):")
        for r in misses:
            print(f"  {r['id']:8s} {r['true']:20s} -> {r['llm_pred']}")

    print(f"\n{'=' * 60}")
    if result["llm_correct"] > result["stub_correct"]:
        print(f"Live model beats the stub by {result['llm_correct'] - result['stub_correct']} cases "
              f"({(result['llm_correct'] - result['stub_correct'])/n:+.1%}).")
    elif result["llm_correct"] < result["stub_correct"]:
        print(f"Live model is WORSE than the stub by {result['stub_correct'] - result['llm_correct']} cases. "
              f"A cheap model is not automatically better than a well-tuned keyword matcher on a small,\n"
              f"templated golden set -- report this honestly rather than assuming the LLM must win.")
    else:
        print("Live model ties the stub exactly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY_SECONDS,
        help=f"seconds to wait between calls, to stay under the rate limit "
             f"(default {DEFAULT_DELAY_SECONDS}s, sized for Groq's free tier)",
    )
    args = parser.parse_args()

    est_minutes = 50 * args.delay / 60
    print(f"Running with a {args.delay}s delay between calls -- ~{est_minutes:.1f} minutes total for 50 cases.\n")

    result = run_comparison(delay_seconds=args.delay)
    print_report(result)

