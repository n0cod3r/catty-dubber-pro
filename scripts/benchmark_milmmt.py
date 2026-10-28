#!/usr/bin/env python3
"""Read-only local translation spike (MiLMMT, HY-MT, LMT); no Catty imports, downloads or integration.

Run with the existing engine environment:
  engine/.venv/bin/python scripts/benchmark_milmmt.py \
    --model-path /absolute/local/model --project /absolute/project.json

Prompt reference: https://huggingface.co/xiaomi-research/MiLMMT-46-1B-v1.0
Outputs are for manual Khmer review, not automatic quality scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

# Set before importing Transformers: even incomplete local bundles must not fetch.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

MODEL_NAME = "MiLMMT-46-1B-v1.0"
REQUIRED = "未婚妻啊啊，"
# Deliberately cover this episode's titles, names, fantasy, fragments and emotion.
ANCHORS = ["陛下", "裴国公赐婚", "性情", "妖精啊", "裴修颜", "人心为食", "山海异兽",
           "水怪", "国公若", "太医", "太夫", "做媳妇", "吗没有", "我叫", "公的未婚"]


def select_segments(segments: list[dict], count: int) -> list[int]:
    required = [i for i, segment in enumerate(segments) if segment["source_text"].strip() == REQUIRED]
    if not required:
        raise ValueError(f"Required line {REQUIRED!r} was not found; select the correct episode")
    chosen = {required[0]}
    for term in ANCHORS:
        match = next((i for i, segment in enumerate(segments)
                      if i not in chosen and term in segment["source_text"]), None)
        if match is not None and len(chosen) < count:
            chosen.add(match)
    # Generic fallback for other projects: spaced samples, preserving stored order.
    for i in sorted(range(len(segments)), key=lambda i: (i * 17) % max(len(segments), 1)):
        if len(chosen) >= count:
            break
        if segments[i]["source_text"].strip():
            chosen.add(i)
    return sorted(chosen)


def make_prompt(current: str, previous: str, following: str, speaker: str, contextual: bool) -> str:
    # Same style instruction and documented language names/template in both modes.
    prefix = "Use natural spoken Khmer. Output only the translation of the current dialogue.\n\n"
    if contextual:
        prefix += (f"Previous:\n{previous or '(none)'}\n\nCurrent:\n{current}\n\n"
                   f"Next:\n{following or '(none)'}\n\nSpeaker:\n{speaker}\n\n"
                   "Translate ONLY Current. Previous and Next are context only; do not translate them.\n\n")
    return prefix + f"Translate this from Chinese (Simplified) to Khmer:\nChinese (Simplified): {current}\nKhmer:"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--count", type=int, default=16, choices=range(10, 21), metavar="10–20")
    parser.add_argument("--episode", type=int, default=0, help="Zero-based stored episode index")
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()
    model_path = args.model_path.expanduser().resolve(strict=True)
    project_path = args.project.expanduser().resolve(strict=True)
    config = json.loads((model_path / "config.json").read_text())
    family = {"gemma3_text": "milmmt", "hunyuan_v1_dense": "hy", "qwen3": "lmt"}.get(config.get("model_type"))
    if family is None:
        parser.error(f"Unsupported benchmark model type: {config.get('model_type')}")
    model_name = model_path.name
    output_path = (args.output or Path("benchmark-results") / f"{model_name.lower()}.json").expanduser().resolve()
    if not model_path.is_dir() or not (model_path / "config.json").is_file():
        parser.error("--model-path must be a local Transformers model folder with config.json")
    if output_path == project_path or output_path.is_relative_to(model_path):
        parser.error("Output must not overwrite the project or any model files")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be positive")
    original = project_path.read_bytes()
    project = json.loads(original)
    episode = project["episodes"][args.episode]
    segments = episode["dialogue_segments"]  # Never reorder by timing.
    indices = select_segments(segments, args.count)
    speakers = {speaker["id"]: speaker["name"] for speaker in episode.get("speakers", [])}

    is_mlx = (model_path / "mlx_manifest.json").is_file()
    torch_version = None
    if is_mlx:
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler
        if args.device not in {"auto", "mps"}:
            parser.error("This MLX benchmark uses the Apple GPU; use --device auto")
        device, dtype = "mlx-metal", "4-bit affine weights, bfloat16 baseline"
    else:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(2)
        torch_version = torch.__version__
        device = args.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        dtype = torch.float32 if device == "cpu" else torch.bfloat16

    def synchronize():
        if is_mlx:
            mx.synchronize()
        elif device == "mps":
            torch.mps.synchronize()
        elif device == "cuda":
            torch.cuda.synchronize()

    print(f"Loading LOCAL {model_name}: {model_path} ({device})", flush=True)
    started = time.perf_counter()
    if is_mlx:
        model, tokenizer = load(model_path, tokenizer_config={"local_files_only": True, "trust_remote_code": False})
        mx.eval(model.parameters())
    else:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False,
                                                 fix_mistral_regex=family == "lmt")
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False, dtype=dtype,
        ).to(device).eval()
    synchronize()
    load_seconds = time.perf_counter() - started

    def prompt_for(current, previous, following, speaker, contextual):
        if family == "milmmt":
            return make_prompt(current, previous, following, speaker, contextual)
        context = (f"Previous:\n{previous or '(none)'}\n\nCurrent:\n{current}\n\n"
                   f"Next:\n{following or '(none)'}\n\nSpeaker:\n{speaker}\n\n"
                   "Translate ONLY Current. Previous and Next are context only.\n\n") if contextual else ""
        if family == "hy":
            content = (context + "参考上面的信息，把下面的文本翻译成高棉语，注意不需要翻译上文，也不要额外解释：\n" + current
                       if contextual else "将以下文本翻译为高棉语，注意只需要输出翻译后的结果，不要额外解释：\n\n" + current)
        else:
            content = context + f"Translate the following text from Chinese into Khmer:\nChinese: {current}\nKhmer:"
        return tokenizer.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                             add_generation_prompt=is_mlx or family == "lmt" or model_name.lower().startswith("hy-mt2"))

    def translate(prompt: str) -> dict:
        synchronize()
        started = time.perf_counter()
        if is_mlx:
            encoded = tokenizer.encode(prompt, add_special_tokens=False)
            pieces = []
            count, limited = 0, False
            for response in stream_generate(model, tokenizer, encoded,
                                            max_tokens=args.max_new_tokens, sampler=make_sampler(temp=0)):
                pieces.append(response.text)
                count = response.generation_tokens
                limited = response.finish_reason == "length"
            text = "".join(pieces).strip()
        else:
            encoded = tokenizer(prompt, add_special_tokens=False, return_token_type_ids=False, return_tensors="pt").to(device)
            with torch.inference_mode():
                generated = model.generate(**encoded, max_new_tokens=args.max_new_tokens, do_sample=False,
                                           pad_token_id=tokenizer.eos_token_id, use_cache=True)
            token_ids = generated[0, encoded["input_ids"].shape[1]:]
            text = tokenizer.decode(token_ids, skip_special_tokens=True).strip()
            count, limited = len(token_ids), len(token_ids) >= args.max_new_tokens
        synchronize()
        elapsed = time.perf_counter() - started
        return {"translation": text, "seconds": elapsed, "generated_tokens": count,
                "hit_token_limit": limited}

    # Exclude initialization/kernel warmup from the timed A/B passes.
    warmup_started = time.perf_counter()
    translate(prompt_for("你好。", "", "", "", False))
    warmup_seconds = time.perf_counter() - warmup_started
    report = {
        "model": model_name, "model_family": family, "model_path": str(model_path), "project": str(project_path),
        "project_sha256": hashlib.sha256(original).hexdigest(), "episode_id": episode["id"],
        "device": device, "dtype": str(dtype), "torch": torch_version,
        "runtime": "mlx-lm" if is_mlx else "transformers",
        "mlx_lm_version": importlib.metadata.version("mlx-lm") if is_mlx else None,
        "experimental_only": True, "promote_to_default": False,
        "transformers": importlib.metadata.version("transformers"), "load_seconds": load_seconds,
        "warmup_seconds": warmup_seconds, "max_new_tokens": args.max_new_tokens,
        "decoding": "greedy, no sampling; alternate A/B execution order per segment",
        "repetition_penalty": 1.0 if is_mlx else model.generation_config.repetition_penalty,
        "prompt_reference": str(model_path / "README.md"),
        "tokenizer_fix_mistral_regex": family == "lmt",
        "add_generation_prompt": is_mlx or family == "lmt" or model_name.lower().startswith("hy-mt2"),
        "settings_note": "Common greedy decoding; HY recommended sampling and LMT example five-beam decoding are not used. Model-specific prompt templates differ.",
        "notes": ["Contextual prompting is experimental; only HY explicitly documents a context template. No output cleanup.",
                  "Existing translations are reference columns only, never included in prompts.",
                  "No duration/timing input, ASR corrections or automatic Khmer quality metrics.",
                  "One run per mode; timings include tokenization, generation and decoding, excluding warmup/load."],
        "results": [],
    }
    for position, index in enumerate(indices):
        segment = segments[index]
        source = segment["source_text"]
        previous = segments[index - 1]["source_text"] if index else ""
        following = segments[index + 1]["source_text"] if index + 1 < len(segments) else ""
        speaker = speakers.get(segment.get("speaker_id"), "Unassigned")
        reference = segment.get("translation") or {}
        prompts = {"no_context": prompt_for(source, previous, following, speaker, False),
                   "contextual": prompt_for(source, previous, following, speaker, True)}
        modes = ["no_context", "contextual"] if position % 2 == 0 else ["contextual", "no_context"]
        outputs = {mode: translate(prompts[mode]) for mode in modes}
        row = {"segment_id": segment["id"], "segment_index": index, "source_text": source,
               "previous_text": previous, "next_text": following, "speaker": speaker,
               "speaker_id": segment.get("speaker_id"), "existing_translation": reference.get("text"),
               "existing_provider": reference.get("provider"), "existing_model": reference.get("model"),
               "no_context_translation": outputs["no_context"]["translation"],
               "contextual_translation": outputs["contextual"]["translation"],
               "inference_times": {mode: outputs[mode]["seconds"] for mode in modes},
               "generation": outputs, "prompts": prompts}
        report["results"].append(row)
        # Save after every pair so a local interruption doesn't lose completed work.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"\n[{position + 1}/{len(indices)}] Chinese: {source}\nSpeaker: {speaker}"
              f"\nPrevious: {previous}\nNext: {following}"
              f"\nExisting {reference.get('provider', 'unavailable')} ({reference.get('model', 'unknown')}): {reference.get('text', '(none)')}"
              f"\n{model_name} no context: {row['no_context_translation']}"
              f"\n{model_name} contextual: {row['contextual_translation']}"
              f"\nInference time: A={outputs['no_context']['seconds']:.2f}s B={outputs['contextual']['seconds']:.2f}s", flush=True)
        if any(output["hit_token_limit"] for output in outputs.values()):
            print("NOTE: A mode reached max_new_tokens; review raw output for truncation.", flush=True)
    times = [row["inference_times"] for row in report["results"]]
    totals = {mode: sum(pair[mode] for pair in times) for mode in ("no_context", "contextual")}
    total = sum(totals.values())
    report["summary"] = {"segments_tested": len(indices), "total_inference_seconds": total,
                         "average_seconds_per_segment_both_modes": total / len(indices),
                         "modes": {mode: {"total_seconds": value, "average_seconds_per_segment": value / len(indices)} for mode, value in totals.items()}}
    report["project_unchanged"] = project_path.read_bytes() == original
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\nModel: {model_name}\nSegments tested: {len(indices)}\nTotal inference time: {total:.2f}s"
          f"\nAverage time/segment (both modes): {total / len(indices):.2f}s"
          f"\nNo context average: {totals['no_context'] / len(indices):.2f}s"
          f"\nContextual average: {totals['contextual'] / len(indices):.2f}s"
          f"\nProject unchanged: {report['project_unchanged']}\nResults: {output_path}", flush=True)


if __name__ == "__main__":
    main()
