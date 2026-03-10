"""
examples/basic_dmaic.py
========================
Exemplo básico: execução do pipeline DMAIC completo.

Demonstra o uso mais simples do SigmaFlow — carregue um dataset e
percorra todas as cinco fases DMAIC com uma única chamada.

Uso
---
    python examples/basic_dmaic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def create_sample_dataset() -> pd.DataFrame:
    """
    Cria um dataset de processo simples para demonstração.

    Returns
    -------
    pd.DataFrame
        Dataset com medições de processo e limites de especificação.
    """
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "measurement": rng.normal(10.0, 0.09, 120),
        "usl": 10.3,
        "lsl": 9.7,
    })


def main() -> None:
    """Executa o pipeline DMAIC básico e imprime os resultados de cada fase."""
    print("=" * 55)
    print("  SigmaFlow — Exemplo Básico DMAIC")
    print("=" * 55)

    # 1. Carregar dataset
    df = create_sample_dataset()
    print(f"\n[1] Dataset carregado: {df.shape[0]} linhas × {df.shape[1]} colunas")

    # 2. Rodar pipeline DMAIC
    from sigmaflow.core.dmaic_engine import DMAICEngine

    print("[2] Executando pipeline DMAIC...")
    engine = DMAICEngine(df)
    result = engine.run_all()

    # 3. Exibir resumo por fase
    phases = {
        "define":  "D — Define",
        "measure": "M — Measure",
        "analyze": "A — Analyze",
        "improve": "I — Improve",
        "control": "C — Control",
    }
    print("\n[3] Resultados por fase:\n")
    for key, label in phases.items():
        phase_data = result.get(key, {})
        print(f"  [{label}]")
        if isinstance(phase_data, dict):
            for k, v in list(phase_data.items())[:4]:
                print(f"    {k:30s}: {str(v)[:70]}")
        print()

    print("Pipeline DMAIC concluído.")


if __name__ == "__main__":
    main()
