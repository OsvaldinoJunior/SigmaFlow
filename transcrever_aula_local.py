"""Transcreve um v?deo local em portugu?s com o ambiente .venv-transcricao."""
import argparse
from pathlib import Path
from faster_whisper import WhisperModel

parser = argparse.ArgumentParser(description="Transcrever uma aula local")
parser.add_argument("video", type=Path)
parser.add_argument("--modelo", default="small")
args = parser.parse_args()
if not args.video.is_file():
    parser.error("Arquivo de v?deo n?o encontrado")
model = WhisperModel(args.modelo, device="cpu", compute_type="int8", cpu_threads=2)
segments, info = model.transcribe(str(args.video), language="pt", vad_filter=True, beam_size=5)
output = args.video.with_suffix(".txt")
with output.open("w", encoding="utf-8") as f:
    for segment in segments:
        seconds = int(segment.start)
        line = f"[{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}] {segment.text.strip()}"
        print(line, flush=True)
        f.write(line + "\n")
        f.flush()
print(f"Transcri??o salva em: {output}")
