#!/usr/bin/env python3
"""
cli.py — SigmaFlow Command-Line Interface
==========================================
Interface de linha de comando para o SigmaFlow.

Comandos disponíveis
---------------------
    sigmaflow run <dataset>       Pipeline completo de análise
    sigmaflow dmaic <dataset>     Pipeline DMAIC (Define→Measure→Analyze→Improve→Control)
    sigmaflow demo                Gera datasets de exemplo e executa análise
    sigmaflow list                Lista os analisadores registrados
    sigmaflow report              Regera o relatório LaTeX/PDF
    sigmaflow insights            Exibe os insights no console
    sigmaflow dashboard           Regera o dashboard HTML
    sigmaflow ingest              Ingere dados de fonte externa (CSV, Excel, SQL, API)
    sigmaflow project             Gerencia projetos (create, list, show)
    sigmaflow schedule            Agenda execuções recorrentes (create, list, disable)

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

ROOT = Path(__file__).resolve().parents[2]
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
    print("  version 0.2.0")
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


# ── Command: run ──────────────────────────────────────────────────────────────

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


# ── Command: dmaic ────────────────────────────────────────────────────────────

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


# ── Command: demo ─────────────────────────────────────────────────────────────

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


# ── Command: list ─────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    """Lista os analisadores registrados no DatasetRegistry."""
    from sigmaflow.core.dataset_registry import DatasetRegistry
    registry = DatasetRegistry().discover()
    print(registry.summary())


# ── Command: report ───────────────────────────────────────────────────────────

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


# ── Command: insights ─────────────────────────────────────────────────────────

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


# ── Command: dashboard ────────────────────────────────────────────────────────

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


# ── Command: ingest ───────────────────────────────────────────────────────────

def cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest data from external source into a project."""
    from sigmaflow.connectors import ConnectorRegistry, ConnectorConfig, IngestionResult
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import Project, Dataset, User

    _banner()

    # Validate project exists
    with get_sync_session() as session:
        project = session.query(Project).filter(Project.code == args.project).first()
        if not project:
            print(f"  ✗ Projeto não encontrado: {args.project}")
            sys.exit(1)

        # Get owner user
        owner = project.owner

        # Build connector config
        connector_config = {}
        if args.config:
            try:
                connector_config = json.loads(args.config)
            except json.JSONDecodeError as e:
                print(f"  ✗ Config JSON inválido: {e}")
                sys.exit(1)

        # Create connector config
        config = ConnectorConfig(
            name=args.name or f"{args.source}_import",
            source_type=args.source,
            config=connector_config
        )

        # Get connector
        registry = ConnectorRegistry()
        connector = registry.create(args.source, config)
        if not connector:
            print(f"  ✗ Conector não disponível: {args.source}")
            print(f"  Conectores disponíveis: {', '.join(registry.list_available())}")
            sys.exit(1)

        # Validate and connect
        valid, error = connector.validate_config()
        if not valid:
            print(f"  ✗ Configuração inválida: {error}")
            sys.exit(1)

        if not connector.connect():
            print(f"  ✗ Falha ao conectar na fonte")
            sys.exit(1)

        # Read data based on source type
        result: IngestionResult
        if args.source in ("csv", "excel"):
            if not args.file:
                print(f"  ✗ --file é obrigatório para source={args.source}")
                sys.exit(1)
            result = connector.read(file_path=args.file)
        elif args.source == "sql":
            if not args.query:
                print(f"  ✗ --query é obrigatório para source=sql")
                sys.exit(1)
            result = connector.read(query=args.query)
        elif args.source == "api":
            if not args.endpoint:
                print(f"  ✗ --endpoint é obrigatório para source=api")
                sys.exit(1)
            result = connector.read(endpoint=args.endpoint)
        else:
            print(f"  ✗ Source não suportado: {args.source}")
            sys.exit(1)

        connector.close()

        if not result.success:
            print(f"  ✗ Falha na ingestão: {result.error}")
            sys.exit(1)

        # Create dataset record
        dataset_name = args.name or Path(args.file or args.endpoint or "query").stem
        dataset = Dataset(
            project_id=project.id,
            name=dataset_name,
            description=args.description or f"Imported from {args.source}",
            version=1,
            source_type=args.source,
            source_config=connector_config,
            file_path=args.file if args.source in ("csv", "excel") else None,
            file_hash=result.file_hash,
            row_count=result.row_count,
            column_count=result.column_count,
            schema_json={"columns": result.columns, "dtypes": result.dtypes},
            created_by_id=owner.id,
        )
        session.add(dataset)
        session.commit()
        session.refresh(dataset)

        print(f"\n  ✅ Dataset ingerido com sucesso!")
        print(f"     ID: {dataset.id}")
        print(f"     Nome: {dataset.name} v{dataset.version}")
        print(f"     Projeto: {project.code}")
        print(f"     Linhas: {result.row_count:,}")
        print(f"     Colunas: {result.column_count}")
        print(f"     Hash: {result.file_hash[:16]}...")


# ── Command: project ──────────────────────────────────────────────────────────

def cmd_project_create(args: argparse.Namespace) -> None:
    """Create a new DMAIC project."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import Project, Plant, User

    _banner()

    with get_sync_session() as session:
        # Check plant exists
        plant = session.query(Plant).filter(Plant.code == args.plant).first()
        if not plant:
            print(f"  ✗ Planta não encontrada: {args.plant}")
            print("  Crie a planta primeiro ou use código existente")
            sys.exit(1)

        # Check owner exists
        owner = session.query(User).filter(User.email == args.owner).first()
        if not owner:
            print(f"  ✗ Usuário não encontrado: {args.owner}")
            sys.exit(1)

        # Check project code unique
        existing = session.query(Project).filter(Project.code == args.code).first()
        if existing:
            print(f"  ✗ Projeto já existe: {args.code}")
            sys.exit(1)

        project = Project(
            code=args.code,
            name=args.name,
            description=args.description,
            plant_id=plant.id,
            owner_id=owner.id,
            problem_statement=args.problem,
            goal_statement=args.goal,
            status="active",
        )
        session.add(project)
        session.commit()

        print(f"\n  ✅ Projeto criado com sucesso!")
        print(f"     Código: {project.code}")
        print(f"     Nome: {project.name}")
        print(f"     Planta: {plant.code} ({plant.name})")
        print(f"     Responsável: {owner.email}")


def cmd_project_list(args: argparse.Namespace) -> None:
    """List projects with optional filters."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import Project, Plant

    _banner()

    with get_sync_session() as session:
        query = session.query(Project).join(Plant)

        if args.plant:
            query = query.filter(Plant.code == args.plant)
        if args.status:
            query = query.filter(Project.status == args.status)

        projects = query.order_by(Project.created_at.desc()).all()

        if not projects:
            print("  Nenhum projeto encontrado.")
            return

        print(f"\n  {'CÓDIGO':<15} {'NOME':<35} {'PLANTA':<15} {'STATUS':<12} {'RESPONSÁVEL':<30}")
        print("  " + "-" * 110)
        for p in projects:
            owner_email = p.owner.email if p.owner else "N/A"
            print(f"  {p.code:<15} {p.name[:34]:<35} {p.plant.code:<15} {p.status:<12} {owner_email[:29]:<30}")


def cmd_project_show(args: argparse.Namespace) -> None:
    """Show project details."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import Project, Dataset, Run, ActionItem

    _banner()

    with get_sync_session() as session:
        project = session.query(Project).filter(Project.code == args.code).first()
        if not project:
            print(f"  ✗ Projeto não encontrado: {args.code}")
            sys.exit(1)

        print(f"\n  Projeto: {project.code} — {project.name}")
        print(f"  Planta: {project.plant.code} ({project.plant.name})")
        print(f"  Responsável: {project.owner.email if project.owner else 'N/A'}")
        print(f"  Status: {project.status}")
        print(f"  Criado em: {project.created_at.strftime('%Y-%m-%d %H:%M')}")
        if project.description:
            print(f"  Descrição: {project.description}")
        if project.problem_statement:
            print(f"  Problema: {project.problem_statement}")
        if project.goal_statement:
            print(f"  Meta: {project.goal_statement}")

        # Datasets
        datasets = session.query(Dataset).filter(Dataset.project_id == project.id, Dataset.is_active == True).all()
        print(f"\n  Datasets ({len(datasets)}):")
        for d in datasets:
            print(f"    • {d.name} v{d.version} — {d.row_count:,} linhas × {d.column_count} cols — {d.source_type}")

        # Recent runs
        runs = session.query(Run).filter(Run.project_id == project.id).order_by(Run.created_at.desc()).limit(5).all()
        print(f"\n  Runs recentes ({len(runs)}):")
        for r in runs:
            print(f"    • Run #{r.run_number} — {r.status.value} — {r.created_at.strftime('%Y-%m-%d %H:%M')}")

        # Open actions
        actions = session.query(ActionItem).filter(
            ActionItem.project_id == project.id,
            ActionItem.status.in_(["open", "in_progress"])
        ).all()
        print(f"\n  Ações abertas/em andamento ({len(actions)}):")
        for a in actions[:5]:
            assignee = a.assignee.email if a.assignee else "Não atribuído"
            print(f"    • [{a.priority}] {a.title[:60]} — {assignee} — venc: {a.due_date.strftime('%Y-%m-%d') if a.due_date else 'N/A'}")


# ── Command: schedule ─────────────────────────────────────────────────────────

def cmd_schedule_create(args: argparse.Namespace) -> None:
    """Create a scheduled run."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import Project, ScheduledRun

    _banner()

    with get_sync_session() as session:
        project = session.query(Project).filter(Project.code == args.project).first()
        if not project:
            print(f"  ✗ Projeto não encontrado: {args.project}")
            sys.exit(1)

        config = {}
        if args.config:
            try:
                config = json.loads(args.config)
            except json.JSONDecodeError as e:
                print(f"  ✗ Config JSON inválido: {e}")
                sys.exit(1)

        schedule = ScheduledRun(
            project_id=project.id,
            cron_expression=args.cron,
            timezone=args.timezone,
            dataset_name=args.dataset,
            run_config=config,
            enabled=True,
        )
        session.add(schedule)
        session.commit()

        print(f"\n  ✅ Agendamento criado!")
        print(f"     ID: {schedule.id}")
        print(f"     Projeto: {project.code}")
        print(f"     Cron: {schedule.cron_expression} ({schedule.timezone})")
        print(f"     Dataset: {schedule.dataset_name or 'Mais recente'}")


def cmd_schedule_list(args: argparse.Namespace) -> None:
    """List scheduled runs."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import ScheduledRun, Project

    _banner()

    with get_sync_session() as session:
        query = session.query(ScheduledRun).join(Project)

        if args.project:
            query = query.filter(Project.code == args.project)

        schedules = query.order_by(ScheduledRun.created_at.desc()).all()

        if not schedules:
            print("  Nenhum agendamento encontrado.")
            return

        print(f"\n  {'ID':<38} {'PROJETO':<15} {'CRON':<20} {'TZ':<20} {'DATASET':<20} {'STATUS'}")
        print("  " + "-" * 120)
        for s in schedules:
            status = "🟢 Ativo" if s.enabled else "🔴 Inativo"
            print(f"  {str(s.id):<38} {s.project.code:<15} {s.cron_expression:<20} {s.timezone:<20} {(s.dataset_name or 'auto'):<20} {status}")


def cmd_schedule_disable(args: argparse.Namespace) -> None:
    """Disable a scheduled run."""
    from sigmaflow.core.database import get_sync_session
    from sigmaflow.core.models import ScheduledRun
    import uuid

    _banner()

    with get_sync_session() as session:
        schedule = session.query(ScheduledRun).filter(ScheduledRun.id == uuid.UUID(args.id)).first()
        if not schedule:
            print(f"  ✗ Agendamento não encontrado: {args.id}")
            sys.exit(1)

        schedule.enabled = False
        session.commit()

        print(f"\n  ✅ Agendamento desabilitado: {args.id}")


# ── Entry-point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Ponto de entrada principal do CLI do SigmaFlow."""
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
  sigmaflow ingest SF-001 --source csv --file data.csv --name "Process Data"
  sigmaflow project create --code SF-001 --name "Redução de Defeitos" --plant SP01 --owner bb@company.com
  sigmaflow schedule create --project SF-001 --cron "0 6 * * *"
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

    # sigmaflow ingest
    p_ingest = sub.add_parser(
        "ingest",
        help="Ingere dados de uma fonte externa (CSV, Excel, SQL, API) para um projeto",
        description="Ingere dados usando conectores e registra como dataset versionado no projeto.",
    )
    p_ingest.add_argument("project", help="Código do projeto (ex: SF-001)")
    p_ingest.add_argument("--source", required=True, choices=["csv", "excel", "sql", "api"], help="Tipo de fonte de dados")
    p_ingest.add_argument("--file", help="Caminho do arquivo (para csv/excel)")
    p_ingest.add_argument("--query", help="Query SQL (para source=sql)")
    p_ingest.add_argument("--endpoint", help="Endpoint da API (para source=api)")
    p_ingest.add_argument("--name", help="Nome do dataset (opcional, usa nome do arquivo/endpoint)")
    p_ingest.add_argument("--description", help="Descrição do dataset")
    p_ingest.add_argument("--config", help="JSON com configuração extra do conector")
    p_ingest.set_defaults(func=cmd_ingest)

    # sigmaflow project
    p_project = sub.add_parser("project", help="Gerencia projetos")
    project_sub = p_project.add_subparsers(dest="project_action", required=True)

    p_project_create = project_sub.add_parser("create", help="Cria novo projeto")
    p_project_create.add_argument("--code", required=True, help="Código do projeto (ex: SF-001)")
    p_project_create.add_argument("--name", required=True, help="Nome do projeto")
    p_project_create.add_argument("--plant", required=True, help="Código da planta")
    p_project_create.add_argument("--owner", required=True, help="Email do responsável (Black Belt)")
    p_project_create.add_argument("--description", help="Descrição do projeto")
    p_project_create.add_argument("--problem", help="Declaração do problema")
    p_project_create.add_argument("--goal", help="Meta do projeto")
    p_project_create.set_defaults(func=cmd_project_create)

    p_project_list = project_sub.add_parser("list", help="Lista projetos")
    p_project_list.add_argument("--plant", help="Filtrar por planta")
    p_project_list.add_argument("--status", help="Filtrar por status")
    p_project_list.set_defaults(func=cmd_project_list)

    p_project_show = project_sub.add_parser("show", help="Mostra detalhes do projeto")
    p_project_show.add_argument("code", help="Código do projeto")
    p_project_show.set_defaults(func=cmd_project_show)

    # sigmaflow schedule
    p_schedule = sub.add_parser("schedule", help="Agenda execuções recorrentes")
    schedule_sub = p_schedule.add_subparsers(dest="schedule_action", required=True)

    p_schedule_create = schedule_sub.add_parser("create", help="Cria agendamento")
    p_schedule_create.add_argument("--project", required=True, help="Código do projeto")
    p_schedule_create.add_argument("--cron", required=True, help="Expressão cron (ex: '0 6 * * *' para 06:00)")
    p_schedule_create.add_argument("--timezone", default="America/Sao_Paulo", help="Timezone do cron")
    p_schedule_create.add_argument("--dataset", help="Dataset específico (opcional, usa o mais recente)")
    p_schedule_create.add_argument("--config", help="JSON com configuração do run")
    p_schedule_create.set_defaults(func=cmd_schedule_create)

    p_schedule_list = schedule_sub.add_parser("list", help="Lista agendamentos")
    p_schedule_list.add_argument("--project", help="Filtrar por projeto")
    p_schedule_list.set_defaults(func=cmd_schedule_list)

    p_schedule_disable = schedule_sub.add_parser("disable", help="Desabilita agendamento")
    p_schedule_disable.add_argument("id", help="ID do agendamento")
    p_schedule_disable.set_defaults(func=cmd_schedule_disable)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()