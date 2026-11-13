"""Gera planilhas fictícias e verifica triagem e cálculo através da API local.

Uso: python scripts/gerar_exemplos_lss.py
Arquivos existentes são preservados. Nenhum dado representa uma empresa real.
"""
from __future__ import annotations

import base64
import json
import sys
import threading
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_app import Handler  # noqa: E402

DEST = ROOT / "problemas_exemplos_testes_LSS"
DAYS = [date(2026, 1, 1) + timedelta(days=i) for i in range(30)]


def example(filename, title, problem, columns, rows, expected, method, parameters=None):
    return {"filename": filename, "title": title, "problem": problem,
            "columns": columns, "rows": rows, "expected": expected, "method": method, "parameters": parameters or {}}


PILOT_PARAMETERS = {"direction": "decrease", "before_start": "2026-01-01", "before_end": "2026-01-10",
                    "after_start": "2026-01-21", "after_end": "2026-01-30", "independence_confirmed": True,
                    "comparability_confirmed": True, "comparability_notes": "Dados fictícios. Suposta mesma população/mix e medição; não há demonstração de independência nem de causalidade."}


CASES = [
    example("01_refugo_retrabalho.xlsx", "Refugo e retrabalho", "Investigar os defeitos que mais contribuem para o refugo.",
            ["Data de produção", "Linha", "Tipo de defeito", "Quantidade rejeitada", "Custo unitário"],
            [[d, "Linha A", ["Vedação", "Rótulo", "Enchimento"][i % 3], [22, 10, 6][i % 3] + i % 4, 4.50] for i, d in enumerate(DAYS)], "refugo", "Pareto por unidades/ocorrencias", {"count_basis":"defective_units"}),
    example("02_taxa_defeitos_tempo.xlsx", "Taxa de defeitos no tempo", "Acompanhar a proporção de unidades rejeitadas por dia.",
            ["Data de produção", "Unidades inspecionadas", "Quantidade rejeitada"],
            [[d, 950 + i % 5 * 20, 18 + (i % 6) * 3] for i, d in enumerate(DAYS)], "atributos", "Carta p", {"count_basis":"defective_units"}),
    example("03_capacidade_dimensional.xlsx", "Capacidade dimensional", "Avaliar o diâmetro de peças frente às especificações.",
            ["Data da medição", "Diâmetro (mm)", "LIE", "LSE"],
            [[d, round(20 + ((i * 7) % 17 - 8) * 0.012, 3), 19.8, 20.2] for i, d in enumerate(DAYS)], "capacidade", "Capacidade de processo"),
    example("04_variacao_temporal.xlsx", "Variação no tempo", "Verificar mudanças no peso de enchimento ao longo dos dias.",
            ["Data da coleta", "Peso (g)"],
            [[d, round(500 + ((i * 11) % 19 - 9) * 0.3 + (2 if i > 22 else 0), 2)] for i, d in enumerate(DAYS)], "spc", "Carta de controle"),
    example("05_comparacao_turnos.xlsx", "Diferenças entre turnos", "Comparar medições de três turnos.",
            ["Turno", "Medição do processo"],
            [[["Manhã", "Tarde", "Noite"][i % 3], round(12 + (i % 3) * 0.15 + ((i * 5) % 7) * 0.03, 2)] for i in range(36)], "grupos", "Comparação de grupos"),
    example("06_msa_gauge_rr.xlsx", "Sistema de medição", "Avaliar medições repetidas das mesmas peças por operadores.",
            ["Identificação da peça", "Operador", "Repetição", "Resultado da medição"],
            [[f"P{part:02}", op, rep, round(10 + part * 0.05 + (0.01 if op == "B" else 0) + rep * 0.002, 3)] for part in range(1, 11) for op in ["A", "B", "C"] for rep in [1, 2]], "msa", "Gauge R&R"),
    example("07_fmea_processo.xlsx", "FMEA de processo", "Priorizar modos de falha para discussão pela equipe.",
            ["Modo de falha", "Severidade", "Ocorrência", "Detecção"],
            [[mode, severity, occurrence, detection] for mode, severity, occurrence, detection in [("Falta de vedação", 8, 5, 4), ("Rótulo incorreto", 6, 4, 5), ("Volume baixo", 7, 3, 4), ("Tampa danificada", 5, 5, 3)]], "fmea", "FMEA"),
    example("08_fatores_experimento.xlsx", "Fatores e experimento", "Explorar a relação entre temperatura e medição; revisar o desenho experimental.",
            ["Temperatura (°C)", "Medição", "Repetição"],
            [[temp, round(80 + (temp - 160) * 0.22 + rep * 0.15, 2), rep] for temp in [150, 160, 170] for rep in range(1, 7)], "doe", "Exploração por fator"),
    example("09_paradas_oee.xlsx", "Paradas e eficiência", "Analisar perdas de tempo e dados necessários para OEE.",
            ["Data do registro", "Tempo planejado (minutos)", "Tempo de parada (minutos)", "Quantidade produzida", "Quantidade rejeitada", "Ciclo ideal (minutos por peça)"],
            [[d, 480, 25 + (i % 4) * 5, 800 - (i % 4) * 12, 8 + i % 5, 0.5] for i, d in enumerate(DAYS)], "oee", "OEE"),
    example("10_fluxo_lead_time.xlsx", "Fluxo e lead time", "Comparar o tempo de atendimento entre etapas do fluxo.",
            ["Etapa do processo", "Lead time (minutos)"],
            [[["Separação", "Inspeção", "Expedição"][i % 3], 25 + (i % 3) * 15 + i % 7] for i in range(45)], "fluxo", "Distribuição de tempos"),
    example("11_energia_por_producao.xlsx", "Energia por produção", "Investigar consumo de energia em relação ao volume produzido.",
            ["Data do registro", "Consumo de energia (kWh)", "Unidades produzidas"],
            [[d, round(450 + (i % 8) * 13 + (i % 3) * 4, 1), 1000 + (i % 8) * 35] for i, d in enumerate(DAYS)], "energia", "Consumo por unidade"),
    example("12_falhas_confiabilidade.xlsx", "Falhas e confiabilidade", "Investigar o histórico de falhas de equipamentos.",
            ["Data da falha", "Equipamento", "Falha", "Tempo até falha (horas)"],
            [[d, f"Bomba {i % 3 + 1}", ["Selo", "Motor", "Rolamento"][i % 3], 180 + i * 12] for i, d in enumerate(DAYS)], "confiabilidade", "Contagem de falhas por ativo"),
    example("13_vida_util_censurada.xlsx", "Vida útil com censura à direita", "Acompanhar 12 válvulas independentes: uma linha por unidade, tempo em horas, evento 1 = falha observada e 0 = censura à direita; mesma origem de tempo e censura não informativa assumidas.",
            ["Ativo", "Tempo observado (horas)", "Evento"],
            [[f"Valvula-{i+1:02}", time, event] for i, (time, event) in enumerate(zip(
                [120, 120, 180, 210, 250, 270, 300, 330, 350, 400, 420, 500],
                [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 0]))], "sobrevivencia", "Kaplan–Meier"),
    example("14_piloto_refugo_antes_depois.xlsx", "Piloto de refugo com meta pontual atingida", "Comparar proporções com denominadores; dias 11 a 20 são transição excluída. As declarações de independência/comparabilidade são hipóteses do exemplo fictício.",
            ["Data da coleta", "Quantidade rejeitada", "Unidades inspecionadas"],
            [[d, (40 if i < 10 else 20 if i >= 20 else 30) + i % 3, 1000 + i % 2 * 100] for i, d in enumerate(DAYS)],
            "piloto", "Proporções: Wilson e Newcombe", dict(PILOT_PARAMETERS, kind="proportion", target=2.5, unit="%", indicator="Refugo", definition="Unidades defeituosas divididas pelo total inspecionado, sem contar uma unidade duas vezes.")),
    example("15_piloto_medicao_meta_pendente.xlsx", "Piloto de medição com meta pendente", "Comparar média de tempo antes/depois; mesmo com mudança observada a estimativa depois não atende a meta 9,5 min. Transição dias 11 a 20 excluída.",
            ["Data da coleta", "Medição do processo"],
            [[d, round((12 if i < 10 else 9.5 if i >= 20 else 11) + 0.3 * (i % 5), 2)] for i, d in enumerate(DAYS)],
            "piloto", "Comparação de médias: Welch", dict(PILOT_PARAMETERS, kind="continuous", target=9.5, unit="min", indicator="Tempo de atendimento", definition="Minutos por unidade independente, com mesmo início/fim de medição nos períodos.")),
]


def write_example(case):
    path = DEST / case["filename"]
    if path.exists():
        return
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Dados"
    sheet.append(case["columns"])
    for row in case["rows"]:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="17483F")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[1].height = 30
    for index, name in enumerate(case["columns"], 1):
        sheet.column_dimensions[get_column_letter(index)].width = min(34, max(17, len(name) + 3))
    notes = workbook.create_sheet("Sobre o exemplo")
    for row in [["Cenário", case["title"]], ["Problema fictício", case["problem"]],
                ["Caminho esperado", case["method"]],
                ["Uso", "Os dados são fictícios. A triagem sugere caminhos; a escolha e validação são do usuário."],
                ["Leitura", "A interface carrega a primeira aba (Dados)."]]:
        notes.append(row)
    notes.column_dimensions["A"].width = 22
    notes.column_dimensions["B"].width = 100
    for cell in notes["A"]:
        cell.font = Font(bold=True, color="17483F")
    for key, value in case["parameters"].items():
        notes.append([f"Parâmetro: {key}", value])
    workbook.save(path)


class QuietHandler(Handler):
    def log_message(self, format, *args):
        return


def api(port, filename, content, mapping=None, scenario=None, parameters=None):
    payload = json.dumps({"filename": filename, "content": base64.b64encode(content).decode("ascii"),
                          "mapping": mapping or {}, "scenario": scenario, "parameters": parameters or {}}, ensure_ascii=False).encode("utf-8")
    route = "analises" if scenario else "diagnostico"
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/{route}", data=payload,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    DEST.mkdir(exist_ok=True)
    for case in CASES:
        write_example(case)

    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = []
    checks = []
    try:
        for case in CASES:
            try:
                result = api(server.server_port, case["filename"], (DEST / case["filename"]).read_bytes())
                match = next(item for item in result["suggestions"] if item["id"] == case["expected"])
                passed = match["status"] == "revisar" and case["method"] in match["methods"]
                detail = "identificado para revisão" if passed else "faltam: " + ", ".join(match["missing"])
                if passed:
                    mapping = {role["id"]: role["selected"] for role in result["roles"]}
                    calculation = api(server.server_port, case["filename"], (DEST / case["filename"]).read_bytes(), mapping, case["expected"], case["parameters"])
                    passed = bool(calculation.get("metodo") and calculation.get("evidencias"))
                    detail = f"triagem e execução: {calculation.get('metodo', 'sem método')}"
                if result.get("warning"):
                    detail += "; aviso do perfilador: " + result["warning"]
                rows.append((case, passed, detail))
            except Exception as exc:
                rows.append((case, False, "erro: " + str(exc)))

        # Verificações de segurança do diagnóstico: ausência de denominador e
        # ambiguidade de coluna não devem ser interpretadas como confirmação.
        missing = b'data;quantidade rejeitada\n2026-01-01;5\n2026-01-02;8\n'
        result = api(server.server_port, "sem_total.csv", missing)
        attr = next(item for item in result["suggestions"] if item["id"] == "atributos")
        checks.append(("Taxa sem quantidade inspecionada", attr["status"] == "faltam dados"))
        ambiguous = b'linha;turno;medicao\nA;Dia;10.1\nB;Noite;10.2\n'
        result = api(server.server_port, "grupos.csv", ambiguous)
        group = next(item for item in result["roles"] if item["id"] == "grupo")
        checks.append(("Linha e turno geram pedido de escolha", group["selected"] is None and len(group["candidates"]) == 2))
        result = api(server.server_port, "grupos.csv", ambiguous, {"grupo": "linha"})
        group_result = next(item for item in result["suggestions"] if item["id"] == "grupos")
        checks.append(("Escolha manual atualiza comparação de grupos", group_result["status"] == "revisar"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    lines = ["# Exemplos fictícios e verificação do SigmaFlow", "",
             "As planilhas são fictícias e a primeira aba contém os dados usados pela interface. "
             "Abra uma planilha por vez na tela local. A segunda aba explica o cenário.", "",
             "A verificação envia cada arquivo aos endpoints de diagnóstico e análise da interface, "
             "usa o mapeamento automático e confere a sugestão e a execução do cenário esperado. "
             "Os pilotos usam parâmetros explicitamente definidos na segunda aba; não são inferidos da planilha.", "",
             "| Arquivo | Problema fictício | Caminho esperado | Resultado da triagem |", "|---|---|---|---|"]
    for case, passed, detail in rows:
        lines.append(f"| [{case['filename']}]({case['filename']}) | {case['title']} | {case['method']} | {'OK' if passed else 'NÃO PASSOU'} — {detail} |")
    lines.extend(["", "## Verificações adicionais", ""])
    for title, passed in checks:
        lines.append(f"- {'OK' if passed else 'NÃO PASSOU'} — {title}.")
    lines.extend(["", "## Como interpretar", "",
                  "OK indica leitura, sugestão e execução do caminho esperado; não comprova validade estatística ou adequação ao contexto industrial. "
                  "A triagem ainda depende do nome das colunas e não comprova causas, adequação das análises ou qualidade dos dados. "
                  "Confira o mapeamento e os pressupostos na interface.", "",
                  "Para repetir a verificação, execute `python scripts/gerar_exemplos_lss.py` na pasta do projeto. "
                  "Planilhas já existentes são preservadas; o relatório de resultados é atualizado.", ""])
    (DEST / "RESULTADO_VERIFICACAO.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Planilhas: {len(rows)}; aprovadas: {sum(passed for _, passed, _ in rows)}; verificações adicionais: {sum(passed for _, passed in checks)}/{len(checks)}")
    for case, passed, detail in rows:
        print(f"{'OK' if passed else 'FALHOU'} {case['filename']}: {detail}")
    for title, passed in checks:
        print(f"{'OK' if passed else 'FALHOU'} {title}")
    if not all(passed for _, passed, _ in rows) or not all(passed for _, passed in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
