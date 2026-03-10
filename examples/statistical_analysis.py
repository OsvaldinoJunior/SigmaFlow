"""
examples/statistical_analysis.py
==================================
Exemplo de uso direto dos módulos estatísticos do SigmaFlow.

Demonstra como usar os módulos de estatística individualmente,
sem passar pelo pipeline automático:
- compute_capability (Cp, Cpk, DPMO)
- compute_xmr_chart (controle XmR)
- compute_pareto (análise 80/20)
- run_normality_tests (Shapiro-Wilk, Anderson-Darling)
- HypothesisTester (t-test, ANOVA)
- RulesEngine (insights automáticos)

Uso
---
    python examples/statistical_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def section(title: str) -> None:
    """Imprime um cabeçalho de seção formatado."""
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


def demo_capability() -> None:
    """
    Demonstra análise de capacidade de processo (Cp, Cpk, DPMO).

    Computa índices de capacidade para um processo bem centrado
    e para um processo fora de especificação.
    """
    from sigmaflow.analysis.capability_analysis import compute_capability, dpmo_to_sigma

    section("1. Análise de Capacidade de Processo")

    rng = np.random.default_rng(42)

    # Processo capaz
    series_ok = pd.Series(rng.normal(10.0, 0.07, 300))
    result_ok = compute_capability(series_ok, usl=10.3, lsl=9.7)
    print(f"\n  Processo CAPAZ (σ = 0.07):")
    print(f"    Cp  = {result_ok['Cp']:.3f}")
    print(f"    Cpk = {result_ok['Cpk']:.3f}")
    print(f"    DPMO = {result_ok['dpmo']:.1f}")
    print(f"    Sigma level = {result_ok['sigma_level']:.2f}σ")

    # Processo incapaz
    series_bad = pd.Series(rng.normal(10.0, 0.45, 300))
    result_bad = compute_capability(series_bad, usl=10.3, lsl=9.7)
    print(f"\n  Processo INCAPAZ (σ = 0.45):")
    print(f"    Cpk = {result_bad['Cpk']:.3f}  ← abaixo de 1.0, ação necessária")
    print(f"    DPMO = {result_bad['dpmo']:.0f}")
    print(f"    Sigma level = {result_bad['sigma_level']:.2f}σ")

    # Conversão DPMO → Sigma
    print(f"\n  Referência DPMO → Sigma:")
    for dpmo, expected in [(3.4, "6σ"), (233, "5σ"), (6210, "4σ"), (66807, "3σ")]:
        sigma = dpmo_to_sigma(dpmo)
        print(f"    DPMO {dpmo:>7,.1f} → {sigma:.1f}σ  ({expected})")


def demo_spc() -> None:
    """
    Demonstra análise de controle estatístico de processo (XmR).

    Cria uma série com drift intencional e detecta o ponto de mudança
    através dos limites UCL/LCL e pontos fora de controle.
    """
    from sigmaflow.analysis.spc_analysis import compute_xmr_chart, compute_trend

    section("2. Cartas de Controle SPC (XmR)")

    rng    = np.random.default_rng(1)
    values = rng.normal(5.0, 0.2, 80)
    values[55:] += 0.7   # drift a partir da observação 55

    series = pd.Series(values)
    result = compute_xmr_chart(series)
    chart  = result["x_chart"]

    print(f"\n  Série: 80 obs, drift introduzido na obs. 55")
    print(f"  CL  = {chart['CL']:.4f}")
    print(f"  UCL = {chart['UCL']:.4f}")
    print(f"  LCL = {chart['LCL']:.4f}")
    print(f"  Pontos fora de controle: {chart.get('n_ooc', 0)}")
    ooc = chart.get("ooc_points", [])[:5]
    if ooc:
        print(f"  Índices OOC (primeiros 5): {ooc}")

    trend = compute_trend(series)
    print(f"\n  Tendência detectada: {trend['direction'].upper()}")
    print(f"  Spearman r = {trend.get('spearman_r', 'N/A')}")


def demo_pareto() -> None:
    """
    Demonstra análise de Pareto (regra 80/20) para defeitos.

    Identifica os tipos de defeito que representam a maioria das
    ocorrências (vital few) e calcula percentuais cumulativos.
    """
    from sigmaflow.analysis.pareto_analysis import compute_pareto

    section("3. Análise de Pareto (80/20)")

    df = pd.DataFrame({
        "tipo_defeito": ["Dimensional", "Superfície", "Solda", "Montagem",
                         "Material", "Embalagem", "Rótulo"],
        "ocorrencias":  [420, 310, 180, 130, 85, 55, 30],
    })
    result = compute_pareto(df, "tipo_defeito", "ocorrencias")

    print(f"\n  Total de defeitos : {result['total']}")
    print(f"  Vital few (≥80%)  : {result['vital_few']}")
    print(f"\n  Ranking:")
    for cat, count, pct_cum in zip(
        result["categories"], result["counts"], result["cumulative_pct"]
    ):
        bar = "█" * int(count / 15)
        print(f"    {cat:15s} {count:4d}  {pct_cum:5.1f}%  {bar}")


def demo_normality() -> None:
    """
    Demonstra testes de normalidade (Shapiro-Wilk).

    Testa uma distribuição normal e uma distribuição exponencial
    para comparar o comportamento dos testes.
    """
    from sigmaflow.analysis.capability_analysis import compute_normality

    section("4. Testes de Normalidade")

    rng = np.random.default_rng(3)

    normal_data = pd.Series(rng.normal(0, 1, 200), name="normal")
    exp_data    = pd.Series(rng.exponential(2, 200), name="exponential")

    for series in [normal_data, exp_data]:
        result = compute_normality(series)
        verdict = "✓ Normal" if result["normal"] else "✗ Não-normal"
        print(f"\n  {series.name:15s} → {verdict}")
        print(f"    {result['test']} W={result['statistic']:.4f}  p={result['p_value']:.4f}")


def demo_rules_engine() -> None:
    """
    Demonstra o motor de regras para insights automáticos.

    Cria um processo com violação de capability (Cpk < 1.0) e
    verifica que o RulesEngine gera um insight crítico.
    """
    from sigmaflow.insights.rules_engine import RulesEngine

    section("5. Motor de Regras — Insights Automáticos")

    rng = np.random.default_rng(5)
    df  = pd.DataFrame({"measurement": rng.normal(10.0, 0.4, 100)})
    analysis = {
        "capability": {
            "Cpk": 0.52, "Cp": 0.55,
            "dpmo": 98340, "sigma_level": 2.8,
            "usl": 10.3, "lsl": 9.7,
        }
    }

    engine   = RulesEngine()
    insights = engine.evaluate(df, analysis, "capability")

    print(f"\n  {len(insights)} insight(s) gerado(s):\n")
    for ins in insights:
        sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(ins.severity, "⚪")
        print(f"  {sev_icon} [{ins.severity.upper()}] {ins.rule}")
        print(f"     {ins.description}")
        print(f"     → {ins.recommendation}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Executa todos os exemplos de análise estatística em sequência."""
    print("=" * 55)
    print("  SigmaFlow — Análise Estatística Modular")
    print("=" * 55)

    demo_capability()
    demo_spc()
    demo_pareto()
    demo_normality()
    demo_rules_engine()

    print("\n" + "=" * 55)
    print("  Todos os exemplos concluídos.")
    print("=" * 55)


if __name__ == "__main__":
    main()
