"""
examples/manufacturing_example.py
===================================
Exemplo de processo de manufatura: análise completa com Engine.

Demonstra o fluxo real de uso do SigmaFlow em um contexto de manufatura:
- Dataset de processo com temperatura, pressão, velocidade e espessura
- Detecção automática de tipo (capability)
- Análise Cp/Cpk, DPMO, regressão e root cause
- Geração de gráficos e relatório

Uso
---
    python examples/manufacturing_example.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "output"
INPUT_DIR  = ROOT / "input" / "datasets"


def generate_manufacturing_data(n: int = 200, seed: int = 7) -> pd.DataFrame:
    """
    Gera dados sintéticos de um processo de manufatura.

    Simula a espessura de um revestimento influenciada por temperatura,
    pressão e velocidade da linha de produção.

    Parameters
    ----------
    n : int
        Número de observações (padrão: 200).
    seed : int
        Semente aleatória para reprodutibilidade.

    Returns
    -------
    pd.DataFrame
        Dataset com variáveis de processo e resposta de qualidade.
    """
    rng = np.random.default_rng(seed)

    temperature = rng.normal(185.0, 4.0, n)
    pressure    = rng.normal(12.0, 0.9, n)
    speed       = rng.uniform(80, 120, n)
    shift       = rng.choice(["A", "B", "C"], size=n)

    # Espessura: influenciada por temperatura e pressão
    thickness = (
        10.0
        + 0.025 * (temperature - 185)
        - 0.060 * (pressure - 12)
        + 0.008 * (speed - 100)
        + rng.normal(0, 0.11, n)
    )

    return pd.DataFrame({
        "temperature_c": temperature.round(2),
        "pressure_bar":  pressure.round(3),
        "speed_rpm":     speed.round(1),
        "shift":         shift,
        "thickness_mm":  thickness.round(4),
        "usl":           10.35,
        "lsl":           9.65,
    })


def main() -> None:
    """
    Executa o pipeline de análise de manufatura completo.

    Etapas:
    1. Gera dataset de processo
    2. Salva em input/datasets/
    3. Executa Engine com análise estatística completa
    4. Imprime Cp, Cpk, DPMO, regressão e insights
    """
    print("=" * 60)
    print("  SigmaFlow — Exemplo de Manufatura")
    print("=" * 60)

    # 1. Gerar e salvar dataset
    print("\n[1] Gerando dataset de processo de manufatura...")
    df   = generate_manufacturing_data(n=200)
    path = INPUT_DIR / "manufacturing_process.xlsx"
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    print(f"    Shape : {df.shape[0]} linhas × {df.shape[1]} colunas")
    print(f"    Salvo : {path.name}")

    # 2. Rodar pipeline
    print("\n[2] Executando análise SigmaFlow...")
    from sigmaflow.core.engine import Engine

    engine  = Engine(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR,
                     run_statistics=True, run_dashboard=True)
    results = engine.run()

    if not results:
        print("  Nenhum resultado. Verifique o diretório de entrada.")
        return

    # 3. Exibir resultados de capability
    print("\n[3] Resultados de Capacidade de Processo:\n")
    for r in results:
        cap = r.get("analysis", {}).get("capability", {})
        if cap:
            print(f"  Dataset : {r['name']}")
            print(f"  Cp      = {cap.get('Cp', 'N/A')}")
            print(f"  Cpk     = {cap.get('Cpk', 'N/A')}")
            print(f"  DPMO    = {cap.get('dpmo', 'N/A')}")
            print(f"  Sigma   = {cap.get('sigma_level', 'N/A')}σ")

        # Regressão
        adv = r.get("advanced", {})
        reg = adv.get("regression", {})
        if reg and "r2" in reg:
            print(f"\n  Regressão R² = {reg['r2']:.4f}")
            sig = reg.get("significant_vars", [])
            if sig:
                print(f"  Preditores significativos: {', '.join(sig)}")

        # Root cause
        rca = r.get("root_cause", {})
        ranked = rca.get("ranked_variables", [])[:3]
        if ranked:
            print("\n  Root Cause (top 3 correlações):")
            for v in ranked:
                print(f"    {v['variable']:20s} r = {v['pearson_r']:+.3f}  [{v['strength']}]")

        # Insights
        insights = r.get("insights", [])[:4]
        if insights:
            print("\n  Insights:")
            for ins in insights:
                print(f"    → {ins}")

    print(f"\n[4] Outputs em: {OUTPUT_DIR}/")
    print("    Abra output/dashboard/report.html no navegador.")


if __name__ == "__main__":
    main()
