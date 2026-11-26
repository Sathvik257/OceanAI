# Local model setup and provenance

The reference runtime is llama.cpp with Qwen3-4B-Instruct-2507, using Unsloth's Q4_K_M GGUF conversion. Model files are deliberately excluded from the repository.

- Original model: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- GGUF source: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- Filename: `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- Downloaded file SHA-256: `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`
- Runtime source: https://github.com/ggml-org/llama.cpp/releases/tag/b12722
- Windows runtime archives: `llama-b12722-bin-win-cpu-x64.zip` (fallback) and `llama-b12722-bin-win-vulkan-x64.zip` (reference run).
- Reference demo server parameters: context 6144, batch and microbatch 128, six CPU threads, one inference slot, GPU layers 99 on Intel Iris Xe through Vulkan, loopback-only port 8080, alias `qwen3-4b-instruct-2507`. The earlier diagnostic runs used context 8192 and default batch allocation; the smaller allocation reduces laptop memory pressure without changing model weights.
- Generation parameters: temperature 0, seed 42, JSON-schema-constrained output and per-stage output caps.

These settings improve repeatability but do not guarantee identical outputs across runtime versions or hardware. The raw request and response are retained for every recorded call. Qwen weights have their own license; consult the model repository before redistribution or use beyond this exercise.

The startup script limits the server's host prompt cache to 512 MiB (`--cache-ram 512`). The workshop run used llama.cpp's default 8192 MiB limit. During the next intake the server had about 5.34 GiB of private memory, with only about 0.97 GiB resident; the initial coastal request was stopped and preserved under `experiments/coastal-cache-pressure/` before restarting with the smaller cache. This changes cache capacity, not model weights, context size, or generation limits. No speedup is claimed without a corresponding measurement.

Initial experiments used the official Qwen2.5 1.5B and 3B Q4_K_M models. They failed requirements, coverage or judge checks. Those interrupted runs remain separately labeled under `experiments/`; their outputs must not be presented as successful demonstrations. The 3B file hash was `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`.

## Alternative: Ollama

Install Ollama using its official distribution and run `ollama pull qwen3:4b-instruct-2507-q4_K_M`. Use `--endpoint http://127.0.0.1:11434 --model qwen3:4b-instruct-2507-q4_K_M` on both build and chat commands. The code supports Ollama's native JSON schema format. The llama.cpp path is the reference execution; Ollama transport is not claimed as an independently completed demonstration. Results from a different runtime should be treated as new runs rather than assumed identical to the committed evidence.

Official API references:

- https://docs.ollama.com/capabilities/structured-outputs
- https://github.com/ggml-org/llama.cpp/tree/master/tools/server

Only one local model server is needed. A CPU run is slower than a GPU run; keep enough free RAM for the model and context to avoid paging. No paid API key is used.

## Measured runtime comparison

An earlier Qwen2.5 3B benchmark on this laptop, 128 input tokens and 32 generated tokens, one repetition: CPU/six threads processed 19.78 input tokens/s and generated 6.39 tokens/s; Vulkan processed 188.26 input tokens/s and generated 7.72 tokens/s. This is a small hardware diagnostic for the earlier model, not a Qwen3 4B or end-to-end factory latency claim. Longer prompts, shared RAM pressure and other active applications change these rates.
