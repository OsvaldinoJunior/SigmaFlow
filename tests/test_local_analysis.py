"""Verificações com resultados conhecidos para as análises locais."""
from pathlib import Path
import sys
import unittest
import pytest

import pandas as pd
from scipy import stats
import inspect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_analysis import execute
from local_statistics import factor_anova


def metrics(result):
    return dict(result["indicadores"])


class LocalAnalysisTests(unittest.TestCase):
    def test_fator_exibe_anova_exploratoria_e_ressalvas(self):
        df = pd.DataFrame({"fator": ["Baixo"]*5 + ["Alto"]*5,
                           "resposta": [5, 6, 4, 5, 6, 8, 9, 7, 8, 9]})
        result = execute(df, {"fator": "fator", "medida": "resposta"}, "doe")
        values = metrics(result)
        self.assertIn("ANOVA de Welch exploratória", result["metodo"])
        self.assertIn("F observado", values)
        self.assertIn("Eta² descritivo", values)
        self.assertIn("Levene (p; variâncias)", values)
        self.assertTrue(any("Diagnósticos de Levene e Shapiro" in note for note in result["observacoes"]))

    def test_fator_com_variancias_desiguais_usa_welch_e_explica_o_diagnostico(self):
        df = pd.DataFrame({"fator": ["A"]*8 + ["B"]*8,
                           "resposta": [10,11,9,10,10,11,9,10,20,10,25,5,23,7,27,3]})
        result = execute(df, {"fator": "fator", "medida": "resposta"}, "doe")
        values = metrics(result)
        self.assertIn("Welch", result["metodo"])
        levene_p = values["Levene (p; variâncias)"]
        self.assertTrue(levene_p.startswith("<") or float(levene_p.replace(",", ".")) < 0.05)
        self.assertTrue(any("Welch acomoda variâncias diferentes" in note for note in result["observacoes"]))
        if "equal_var" in inspect.signature(stats.f_oneway).parameters:
            reference = stats.f_oneway([10,11,9,10,10,11,9,10], [20,10,25,5,23,7,27,3], equal_var=False)
            raw, reason = factor_anova(df.rename(columns={"resposta": "medida"}))
            self.assertIsNone(reason)
            self.assertAlmostEqual(raw["f"], float(reference.statistic), places=10)
            self.assertAlmostEqual(raw["p"], float(reference.pvalue), places=10)

    def test_fator_com_varios_niveis_corrige_comparacoes_pareadas(self):
        df = pd.DataFrame({"fator": ["A"]*8 + ["B"]*8 + ["C"]*8,
                           "resposta": [10,11,9,10,10,11,9,10,
                                        20,10,25,5,23,7,27,3,
                                        30,31,29,30,30,31,29,30]})
        result = execute(df, {"fator": "fator", "medida": "resposta"}, "doe")
        comparisons = result["comparacoes"]
        self.assertEqual(len(comparisons), 3)
        self.assertTrue(all(item["p_holm"] >= item["p_bruto"] for item in comparisons))
        self.assertTrue(all(item["ic_simultaneo"][0] <= item["diferenca"] <= item["ic_simultaneo"][1] for item in comparisons))
        separated = next(item for item in comparisons if item["grupo_a"] == "A" and item["grupo_b"] == "C")
        self.assertLess(separated["p_holm"], 0.05)
        self.assertNotEqual(result["insight"].find("A vs. C"), -1)
        self.assertTrue(any("Bonferroni" in item for item in result["evidencias"]))
        self.assertTrue(any("ajustados por Holm" in item for item in result["observacoes"]))

    def test_pareto_agrupa_categorias(self):
        df = pd.DataFrame({"tipo": ["A", "B", "A"], "qtd": [2, 3, 4]})
        result = execute(df, {"categoria": "tipo", "defeitos": "qtd"}, "refugo", parameters={"count_basis":"defective_units"})
        self.assertEqual(result["linhas"][0][:2], ["A", 6])
        self.assertEqual(metrics(result)["Total de unidades defeituosas"], 9)
        self.assertEqual(result["grafico"]["itens"][0], {"label": "A", "value": 6})
        self.assertIn("A", result["insight"])

    def test_carta_p_e_limites_variaveis(self):
        df = pd.DataFrame({"dia": ["2026-01-02", "2026-01-01"], "rejeitados": [20, 10], "total": [200, 100]})
        result = execute(df, {"data": "dia", "defeitos": "rejeitados", "total": "total"}, "atributos", parameters={"count_basis":"defective_units"})
        self.assertAlmostEqual(metrics(result)["Taxa global (%)"], 10)
        self.assertEqual(result["linhas"][0][:3], ["2026-01-01", 10, 100])
        self.assertAlmostEqual(result["linhas"][0][5], 19.0, places=3)
        self.assertAlmostEqual(result["linhas"][1][5], 16.364, places=3)
        self.assertEqual([s["nome"] for s in result["grafico"]["series"]], ["Taxa (%)", "LIC (%)", "LSC (%)", "Linha central (%)"])
        self.assertEqual(result["grafico"]["series"][-1]["valores"], [10, 10])

    def test_grafico_limitado_nao_limita_indicadores_ou_insight(self):
        df = pd.DataFrame({"tipo": [f"C{i}" for i in range(15)], "qtd": list(range(1, 16))})
        result = execute(df, {"categoria": "tipo", "defeitos": "qtd"}, "refugo", parameters={"count_basis":"defective_units"})
        self.assertEqual(metrics(result)["Total de unidades defeituosas"], 120)
        self.assertEqual(result["grafico"]["mostrados"], 10)
        self.assertEqual(result["grafico"]["total"], 15)
        self.assertIn("C14", result["insight"])

    def test_empates_em_grupos_nao_sugerem_mais_de_um_vencedor_falso(self):
        df = pd.DataFrame({"grupo": ["A", "B"], "medida": [10, 10]})
        result = execute(df, {"grupo": "grupo", "medida": "medida"}, "grupos")
        self.assertIn("empate", result["insight"])

    def test_carta_i_usa_amplitude_movel(self):
        df = pd.DataFrame({"dia": pd.date_range("2026-01-01", periods=5), "valor": [1, 2, 3, 4, 5]})
        result = execute(df, {"data": "dia", "medida": "valor"}, "spc")
        self.assertAlmostEqual(metrics(result)["Amplitude móvel média"], 1)
        self.assertAlmostEqual(result["linhas"][0][4], 3 + 3 / 1.128, places=4)

    def test_capacidade_reporta_pp_e_ppk(self):
        df = pd.DataFrame({"valor": [8, 9, 10, 11, 12], "minimo": [7] * 5, "maximo": [13] * 5})
        result = execute(df, {"medida": "valor", "lsl": "minimo", "usl": "maximo"}, "capacidade")
        self.assertEqual(metrics(result)["Fora da especificação"], 0)
        indices = dict(result["linhas"])
        self.assertAlmostEqual(indices["Pp preliminar"], 6/(6*pd.Series([8, 9, 10, 11, 12]).std()), places=4)
        self.assertNotIn("Cpk", indices)

    def test_fmea_e_ordenacao(self):
        df = pd.DataFrame({"modo": ["A", "B"], "s": [8, 4], "o": [5, 3], "d": [2, 2]})
        result = execute(df, {"categoria": "modo", "severidade": "s", "ocorrencia": "o", "deteccao": "d"}, "fmea")
        self.assertEqual(result["linhas"][0], ["A", 8, 5, 2, 80])
        with self.assertRaises(ValueError):
            execute(df.assign(s=[11, 4]), {"categoria": "modo", "severidade": "s", "ocorrencia": "o", "deteccao": "d"}, "fmea")

    def test_oee_e_validacao(self):
        df = pd.DataFrame({"parada": [60], "planejado": [480], "total": [700], "defeitos": [70], "ciclo": [0.5]})
        mapping = {"parada": "parada", "tempo_planejado": "planejado", "total": "total", "defeitos": "defeitos", "ciclo_ideal": "ciclo"}
        self.assertAlmostEqual(metrics(execute(df, mapping, "oee"))["OEE (%)"], 65.625, delta=0.0051)
        with self.assertRaises(ValueError):
            execute(df.assign(defeitos=[701]), mapping, "oee")

    def test_msa_exige_estudo_balanceado(self):
        df = pd.DataFrame({"peca": [1, 1, 1, 2], "operador": ["A", "A", "B", "B"], "medida": [1., 1.1, 1., 2.]})
        with self.assertRaisesRegex(ValueError, "balanceado"):
            execute(df, {"peca": "peca", "operador": "operador", "medida": "medida"}, "msa")

    def test_rejeita_denominador_zero_e_lacunas(self):
        df = pd.DataFrame({"dia": ["2026-01-01", "2026-01-02"], "rejeitados": [1, 0], "total": [0, 50]})
        with self.assertRaises(ValueError):
            execute(df, {"data": "dia", "defeitos": "rejeitados", "total": "total"}, "atributos", parameters={"count_basis":"defective_units"})
        with self.assertRaises(ValueError):
            execute(df.assign(total=[10, None]), {"data": "dia", "defeitos": "rejeitados", "total": "total"}, "atributos", parameters={"count_basis":"defective_units"})


if __name__ == "__main__":
    unittest.main()


def test_refugo_requires_explicit_count_semantics_and_cost_denominator():
    df = pd.DataFrame({"category":["A","A","B"],"count":[4,1,3],"line":["L1","L2","L1"],"unit_cost":[2.5,2.5,10.0]})
    with pytest.raises(ValueError, match="unidades defeituosas ou ocorrencias"):
        execute(df,{"categoria":"category","defeitos":"count"},"refugo")
    result=execute(df,{"categoria":"category","defeitos":"count","grupo":"line","custo_unitario":"unit_cost"},"refugo",parameters={"count_basis":"defective_units"})
    assert result["linhas"][0][:2] == ["A",5]
    assert result["linhas_custo"][0][:2] == ["B",30.0]
    assert result["linhas_estratificacao"][0][:2] == ["L1","A"]
    assert result["custo_total"] == 42.5
    assert "unitario_multiplicado" == result["custo_tipo"]
    with pytest.raises(ValueError, match="Custo unitario so pode"):
        execute(df,{"categoria":"category","defeitos":"count","custo_unitario":"unit_cost"},"refugo",parameters={"count_basis":"defect_occurrences"})



def test_carta_np_so_aparece_quando_tamanho_dos_subgrupos_e_constante():
    fixed=pd.DataFrame({"day":pd.date_range("2026-01-01",periods=5),"rejects":[5,5,5,30,5],"inspected":[100]*5})
    result=execute(fixed,{"data":"day","defeitos":"rejects","total":"inspected"},"atributos",parameters={"count_basis":"defective_units"})
    assert result["linhas_np"][0][3] == 10.0
    assert result["linhas_np"][3][5] == "Sim"
    assert metrics(result)["Pontos np além dos limites"] == 1
    variable=fixed.copy(); variable.loc[4,"inspected"]=120
    assert "linhas_np" not in execute(variable,{"data":"day","defeitos":"rejects","total":"inspected"},"atributos",parameters={"count_basis":"defective_units"})



def test_p_and_np_charts_reject_defect_occurrence_counts():
    df=pd.DataFrame({"date":pd.date_range("2026-01-01",periods=5),"count":[1,2,0,1,2],"size":[100]*5})
    with pytest.raises(ValueError,match="unidades defeituosas"):
        execute(df,{"data":"date","defeitos":"count","total":"size"},"atributos",parameters={"count_basis":"defect_occurrences"})
