$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeExe = Join-Path $projectRoot '.runtime/llama-vulkan/llama-server.exe'
$gpuLayers = 99
if (!(Test-Path -LiteralPath $runtimeExe)) {
    $runtimeExe = Join-Path $projectRoot '.runtime/llama/llama-server.exe'
    $gpuLayers = 0
}
$modelFile = Join-Path $projectRoot '.runtime/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
if (!(Test-Path -LiteralPath $runtimeExe) -or !(Test-Path -LiteralPath $modelFile)) {
    throw 'Project-local model files are absent. Use the Ollama setup in README.md, or download official llama.cpp and Qwen GGUF files into .runtime.'
}
& $runtimeExe -m $modelFile --host 127.0.0.1 --port 8080 -c 6144 -b 128 -ub 128 -t 6 -np 1 -ngl $gpuLayers --alias qwen3-4b-instruct-2507
