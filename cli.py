"""
cli.py — SigmaFlow Command-Line Interface
==========================================
Interface de linha de comando para o SigmaFlow.

Comandos disponíveis
--------------------
    sigmaflow run <dataset>       Pipeline completo de análise
    sigmaflow dmaic <dataset>     Pipeline DMAIC (Define→Measure→Analyze→Improve→Control)
    sigmaflow demo                Gera datasets de exemplo e executa análise
    sigmaflow list                Lista os analisadores registrados
    sigmaflow report              Regera o relatório LaTeX/PDF
    sigmaflow insights            Exibe os insights no console
    sigmaflow dashboard           Regera o dashboard HTML

Exemplos
--------
    python cli.py run dataset.xlsx
    python cli.py run input/datasets/process_data.csv
    python cli.py dmaic dataset.xlsx
    python cli.py demo
    python cli.py list

Instalação como comando global
-------------------------------
    pip install -e .
    sigmaflow run dataset.xlsx
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sigmaflow.core.logger import get_logger, log_stage, setup_logging

setup_logging(log_dir=None, level="INFO")
logger = get_logger("sigmaflow.cli")


# ── Banner ────────────────────────────────────────────────────────────────────

def _banner() -> None:
    """Exibe o banner de inicialização do SigmaFlow."""
    print("\n" + "═" * 64)
    print("  SigmaFlow — Automated Lean Six Sigma Analysis Platform")
    print("  version 0.1.0")
    print("═" * 64 + "\n")


# ── Helpers compartilhados ────────────────────────────────────────────────────

def _resolve_input(path_str: str) -> Path:
    """
    Resolve o caminho do dataset informado pelo usuário.

    Se o argumento for um arquivo, copia para input/datasets/ e retorna
    o diretório. Se for um diretório, retorna diretamente.

    Parameters
    ----------
    path_str : str
        Caminho fornecido via CLI para o arquivo ou diretório.

    Returns
    -------
    Path
        Diretório de entrada para o Engine.
    """
    target = Path(path_str).resolve()
    if target.is_file():
        input_dir = ROOT / "input" / "datasets"
        input_dir.mkdir(parents=True, exist_ok=True)
        dest = input_dir / target.name
        if target != dest:
            shutil.copy2(target, dest)
            print(f"  ✓ Arquivo copiado para '{dest}'")
        return input_dir
    elif target.is_dir():
        return target
    else:
        print(f"  ✗ Caminho não encontrado: {target}")
        sys.exit(1)


def _print_summary(results: list) -> None:
    """
    Exibe um resumo dos resultados do pipeline no console.

    Parameters
    ----------
    results : list
        Lista de dicts de resultado retornada pelo Engine.run().
    """
    print("\n" + "─" * 64)
    print("  RESUMO DOS RESULTADOS")
    print("─" * 64)
    for r in results:
        dtype = r.get("dataset_type", "?").upper()
        name  = r.get("name", "?")
        shape = r.get("shape", ("?", "?"))
        elapsed = r.get("elapsed_s", 0)
        print(f"\n  [{dtype}] {name}  ({shape[0]} × {shape[1]})  {elapsed:.1f}s")

        for ins in r.get("insights", [])[:5]:
            print(f"    • {ins}")

        structured = r.get("structured_insights", [])
        n_crit = sum(1 for s in structured if s.get("severity") == "critical")
        n_warn = sum(1 for s in structured if s.get("severity") == "warning")
        if n_crit:
            print(f"    🔴 {n_crit} problema(s) crítico(s)")
        if n_warn:
            print(f"    🟡 {n_warn} aviso(s)")

        rca = r.get("root_cause", {})
        if rca.get("strong_candidates"):
            print(f"    🔍 Causas raiz: {', '.join(rca['strong_candidates'][:3])}")


def _generate_report(results: list, output_dir: Path) -> None:
    """
    Gera o relatório LaTeX/PDF.

    Parameters
    ----------
    results : list
        Resultados do pipeline ou lista carregada de insights.json.
    output_dir : Path
        Diretório raiz de output.
    """
    from sigmaflow.report.latex_report import LatexReportGenerator
    log_stage("Gerando relatório LaTeX")
    gen  = LatexReportGenerator(results, output_dir=output_dir / "reports")
    path = gen.generate()
    print(f"  ✅  Relatório: {path}")


def _print_outputs(output_dir: Path) -> None:
    """Exibe o mapa de arquivos gerados."""
    print(f"\n  📁 Diretório de saída: {output_dir}/")
    print(f"     ├── figures/        Gráficos PNG por dataset")
    print(f"     ├── reports/        Relatório LaTeX + PDF")
    print(f"     ├── dashboard/      Dashboard HTML interativo")
    print(f"     ├── insights.json   Insights estruturados (JSON)")
    print(f"     └── logs/           Arquivos de log\n")


# ── Gerador de demos ──────────────────────────────────────────────────────────

def _generate_demo_datasets(input_dir: Path) -> None:
    """
    Gera 5 datasets sintéticos de demonstração.

    Parameters
    ----------
    input_dir : Path
        Diretório onde os arquivos serão salvos.
    """
    import numpy as np
    import pandas as pd

    input_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    pd.DataFrame({
        "measurement": rng.normal(10.02, 0.08, 200),
        "usl": 10.2, "lsl": 9.8,
    }).to_csv(input_dir / "capability_process.csv", index=False)

    vals = rng.normal(2.5, 0.05, 120)
    vals[80:95] += 0.25
    pd.DataFrame({
        "timestamp": range(1, 121),
        "thickness": vals.round(4),
    }).to_csv(input_dir / "spc_thickness.csv", index=False)

    pd.DataFrame({
        "defect_type": ["Dimensional", "Surface", "Weld", "Assembly",
                        "Material", "Packaging", "Label", "Paint"],
        "count": [320, 280, 195, 140, 95, 60, 45, 30],
    }).to_csv(input_dir / "pareto_defects.csv", index=False)

    dist = rng.uniform(50, 800, 200)
    pd.DataFrame({
        "distance_km":   dist.round(1),
        "delivery_days": (dist / 200 + rng.normal(0, 0.4, 200)).clip(1).round(1),
        "sla_days":      [3 if d < 400 else 5 for d in dist],
    }).to_csv(input_dir / "logistics.csv", index=False)

    temp = rng.normal(75, 5, 300)
    pres = rng.normal(2.5, 0.3, 300)
    spd  = rng.normal(100, 10, 300)
    defects = (0.3 * temp + 0.5 * pres + 0.1 * spd + rng.normal(0, 3, 300)).clip(0).round(1)
    pd.DataFrame({
        "temperature": temp.round(2),
        "pressure":    pres.round(3),
        "speed":       spd.round(1),
        "humidity":    rng.uniform(30, 80, 300).round(1),
        "defects":     defects,
    }).to_csv(input_dir / "process_variables.csv", index=False)

    print(f"  ✓ 5 datasets de demonstração criados em '{input_dir}'")


# ── Comando: run ──────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> None:
    """
    Executa o pipeline completo de análise em um dataset.

    Carrega o arquivo, detecta o tipo, roda as análises estatísticas,
    gera os gráficos, aplica as regras de insight e exporta os relatórios.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.dataset, args.output.
    """
    from sigmaflow.core.engine import Engine
    from sigmaflow.core.dataset_registry import DatasetRegistry

    _banner()
    input_dir  = _resolve_input(args.dataset)
    output_dir = Path(args.output)

    registry = DatasetRegistry().discover()
    print(registry.summary())

    engine  = Engine(input_dir=input_dir, output_dir=output_dir, registry=registry)
    results = engine.run()

    if not results:
        print(f"\n  Nenhum dataset processado. Coloque arquivos CSV/XLSX em '{input_dir}'.\n")
        return

    _print_summary(results)
    _generate_report(results, output_dir)
    _print_outputs(output_dir)


# ── Comando: dmaic ────────────────────────────────────────────────────────────

def cmd_dmaic(args: argparse.Namespace) -> None:
    """
    Executa o pipeline DMAIC completo em um dataset.

    Percorre as cinco fases: Define → Measure → Analyze → Improve → Control,
    gerando entregáveis estruturados para cada fase.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.dataset, args.output.
    """
    from sigmaflow.core.dmaic_engine import DMAICEngine
    import pandas as pd

    _banner()
    target = Path(args.dataset).resolve()
    if not target.exists():
        # Tenta resolver dentro de input/datasets/
        target = ROOT / "input" / "datasets" / args.dataset
    if not target.exists():
        print(f"  ✗ Dataset não encontrado: {args.dataset}")
        sys.exit(1)

    print(f"  📂 Dataset : {target.name}")
    log_stage("Carregando dataset")
    df = pd.read_excel(target) if target.suffix in (".xlsx", ".xls") else pd.read_csv(target)
    print(f"  Shape     : {df.shape[0]} linhas × {df.shape[1]} colunas\n")

    log_stage("Iniciando pipeline DMAIC")
    engine = DMAICEngine(df)
    result = engine.run_all()

    print("\n" + "─" * 64)
    print("  RESULTADOS POR FASE DMAIC")
    print("─" * 64)

    phases = ["define", "measure", "analyze", "improve", "control"]
    labels = {
        "define":  "D — Define",
        "measure": "M — Measure",
        "analyze": "A — Analyze",
        "improve": "I — Improve",
        "control": "C — Control",
    }
    for phase in phases:
        phase_result = result.get(phase, {})
        print(f"\n  [{labels[phase]}]")
        if isinstance(phase_result, dict):
            for k, v in list(phase_result.items())[:6]:
                val_str = str(v)[:80] + ("…" if len(str(v)) > 80 else "")
                print(f"    {k:30s} : {val_str}")
        if phase_result.get("error"):
            print(f"    ⚠ Erro: {phase_result['error']}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "dmaic_results.json"
    out_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )
    print(f"\n  ✅ Resultados salvos em: {out_file}\n")


# ── Comando: demo ─────────────────────────────────────────────────────────────

def cmd_demo(args: argparse.Namespace) -> None:
    """
    Gera datasets de demonstração e executa o pipeline completo.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.output.
    """
    from sigmaflow.core.engine import Engine
    from sigmaflow.core.dataset_registry import DatasetRegistry

    input_dir  = ROOT / "input" / "datasets"
    output_dir = Path(args.output)

    _banner()
    log_stage("Gerando datasets de demonstração")
    _generate_demo_datasets(input_dir)

    registry = DatasetRegistry().discover()
    print(registry.summary())

    engine  = Engine(input_dir=input_dir, output_dir=output_dir, registry=registry)
    results = engine.run()

    _print_summary(results)
    _generate_report(results, output_dir)
    _print_outputs(output_dir)


# ── Comando: list ─────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    """Lista os analisadores registrados no DatasetRegistry."""
    from sigmaflow.core.dataset_registry import DatasetRegistry
    registry = DatasetRegistry().discover()
    print(registry.summary())


# ── Comando: report ───────────────────────────────────────────────────────────

def cmd_report(args: argparse.Namespace) -> None:
    """
    Regera o relatório LaTeX/PDF a partir de um insights.json existente.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.output.
    """
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ insights.json não encontrado em '{insights_file}'")
        print("    Execute 'sigmaflow run <dataset>' primeiro.")
        sys.exit(1)
    with insights_file.open(encoding="utf-8") as f:
        results = json.load(f)
    _generate_report(results, Path(args.output))


# ── Comando: insights ─────────────────────────────────────────────────────────

def cmd_insights(args: argparse.Namespace) -> None:
    """
    Exibe os insights do último pipeline no console.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.output.
    """
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ Nenhum insights.json encontrado em '{insights_file}'")
        print("    Execute 'sigmaflow run <dataset>' primeiro.")
        return

    with insights_file.open(encoding="utf-8") as f:
        data = json.load(f)

    _banner()
    for dataset in data:
        print(f"  [{dataset.get('type','?').upper()}] {dataset.get('dataset','?')}")
        abstract = dataset.get("abstract", "")
        if abstract:
            print(f"    {abstract[:200]}{'...' if len(abstract)>200 else ''}")

        for ins in dataset.get("insights", []):
            sev  = ins.get("severity", "info").upper()
            desc = ins.get("description", "")
            rec  = ins.get("recommendation", "")[:100]
            print(f"\n    [{sev}] {desc}")
            if rec:
                print(f"    → {rec}")
        print()


# ── Comando: dashboard ────────────────────────────────────────────────────────

def cmd_dashboard(args: argparse.Namespace) -> None:
    """
    Regera o dashboard HTML interativo.

    Parameters
    ----------
    args : argparse.Namespace
        Argumentos do CLI: args.output.
    """
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ Nenhum insights.json encontrado em '{insights_file}'")
        print("    Execute 'sigmaflow run <dataset>' primeiro.")
        sys.exit(1)

    log_stage("Gerando Dashboard HTML")
    from sigmaflow.report.html_dashboard import HTMLDashboardGenerator
    with insights_file.open(encoding="utf-8") as f:
        results = json.load(f)
    gen  = HTMLDashboardGenerator(results, output_dir=Path(args.output) / "dashboard")
    path = gen.generate()
    print(f"\n  ✅ Dashboard: {path}")
    print("    Abra no navegador — HTML autocontido.\n")


# ── Entry-point ───────────────────────────────────────────────────────────────

def main() -> None:
    """
    Ponto de entrada principal do CLI do SigmaFlow.

    Cria o parser argparse com todos os subcomandos e despacha a função
    correspondente ao comando solicitado.
    """
    parser = argparse.ArgumentParser(
        prog="sigmaflow",
        description="SigmaFlow — Plataforma Python para Lean Six Sigma / DMAIC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  sigmaflow run dataset.xlsx
  sigmaflow run input/datasets/process_data.csv
  sigmaflow dmaic dataset.xlsx
  sigmaflow demo
  sigmaflow list
        """,
    )
    parser.add_argument(
        "--output", "-o",
        default="output",
        metavar="DIR",
        help="Diretório de saída (padrão: output/)",
    )

    sub = parser.add_subparsers(dest="command", required=True, title="comandos")

    # sigmaflow run <dataset>
    p_run = sub.add_parser(
        "run",
        help="Executa pipeline completo em um dataset",
        description="Analisa um arquivo CSV ou XLSX com o pipeline SigmaFlow completo.",
    )
    p_run.add_argument("dataset", help="Arquivo CSV/XLSX ou diretório com datasets")
    p_run.set_defaults(func=cmd_run)

    # sigmaflow dmaic <dataset>
    p_dmaic = sub.add_parser(
        "dmaic",
        help="Executa pipeline DMAIC (Define→Measure→Analyze→Improve→Control)",
        description="Percorre as 5 fases DMAIC e gera entregáveis estruturados.",
    )
    p_dmaic.add_argument("dataset", help="Arquivo CSV/XLSX para análise DMAIC")
    p_dmaic.set_defaults(func=cmd_dmaic)

    # sigmaflow demo
    p_demo = sub.add_parser("demo", help="Gera 5 datasets de exemplo e executa análise completa")
    p_demo.set_defaults(func=cmd_demo)

    # sigmaflow list
    p_list = sub.add_parser("list", help="Lista os analisadores de dataset registrados")
    p_list.set_defaults(func=cmd_list)

    # sigmaflow report
    p_report = sub.add_parser("report", help="Regera o relatório LaTeX/PDF")
    p_report.set_defaults(func=cmd_report)

    # sigmaflow insights
    p_insights = sub.add_parser("insights", help="Exibe os insights no console")
    p_insights.set_defaults(func=cmd_insights)

    # sigmaflow dashboard
    p_dashboard = sub.add_parser("dashboard", help="Regera o dashboard HTML")
    p_dashboard.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
