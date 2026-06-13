"""
Portugal Data Intelligence — Cross-Pillar Rule-Based Insights (Portuguese)
==========================================================================
Portuguese mirror of ``cross_pillar_insights.py``. Same relationship logic and
data points; only the prose is in Portuguese.
"""

from typing import Dict

from src.utils.db import get_connection


def _safe(value, fmt: str = ".1f") -> str:
    """Format a numeric value safely, returning 'N/A' on failure."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):{fmt}}"
    except (TypeError, ValueError):
        return str(value)


def generate_rule_based_cross_pillar(summaries: Dict[str, dict], db_path: str) -> dict:
    """Produce cross-pillar narrative (Portuguese) using economic relationships."""
    relationships = []
    s = _safe

    # 1. Unemployment-GDP (Okun's Law)
    gdp = summaries.get("gdp", {})
    unemp = summaries.get("unemployment", {})
    if gdp.get("status") == "ok" and unemp.get("status") == "ok":
        gdp_growth = gdp.get("recent_avg_growth")
        unemp_trend = unemp.get("trend")
        unemp_latest = unemp.get("latest_value")
        if gdp_growth is not None and gdp_growth > 2 and unemp_trend == "decreasing":
            narrative = (
                f"A relação da Lei de Okun está a funcionar como esperado: o crescimento do "
                f"PIB a rondar {s(gdp_growth)}% tem sido acompanhado por um desemprego em "
                f"queda (atualmente {s(unemp_latest)}%). O mercado de trabalho está a "
                f"absorver a expansão do produto, consistente com um nexo "
                f"crescimento-emprego saudável."
            )
            strength = "strong"
        elif gdp_growth is not None and gdp_growth > 0 and unemp_trend != "decreasing":
            narrative = (
                f"Está a emergir uma desconexão entre o crescimento do PIB ({s(gdp_growth)}%) "
                f"e o mercado de trabalho (tendência do desemprego: {unemp_trend}). Este "
                f"padrão de 'crescimento sem emprego' pode indicar desajustamentos "
                f"estruturais, maior automação ou rigidezes do mercado de trabalho que "
                f"impedem os ganhos de produto de se traduzirem em criação de emprego."
            )
            strength = "weak"
        else:
            narrative = (
                f"Tanto os indicadores do PIB como do emprego sugerem fraqueza económica. Um "
                f"crescimento do PIB de {s(gdp_growth)}% é insuficiente para impulsionar uma "
                f"redução significativa do desemprego. A economia pode estar a operar num "
                f"equilíbrio de baixo crescimento."
            )
            strength = "consistent_weakness"
        relationships.append(
            {
                "name": "Nexo PIB-Desemprego (Lei de Okun)",
                "pillars": ["gdp", "unemployment"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    # 2. Interest Rates-Credit Transmission
    ir = summaries.get("interest_rates", {})
    credit = summaries.get("credit", {})
    if ir.get("status") == "ok" and credit.get("status") == "ok":
        ir_trend = ir.get("trend")
        credit_trend = credit.get("trend")
        if ir_trend == "decreasing" and credit_trend == "increasing":
            narrative = (
                "A transmissão da política monetária parece eficaz: a descida das taxas de "
                "juro tem sido acompanhada por uma expansão do crédito. A postura "
                "acomodatícia do BCE está a baixar com sucesso os custos de financiamento e "
                "a estimular a concessão de crédito em Portugal."
            )
            strength = "strong"
        elif ir_trend == "decreasing" and credit_trend != "increasing":
            narrative = (
                f"Apesar da descida das taxas de juro, o crédito não se expandiu como "
                f"esperado (tendência do crédito: {credit_trend}). Esta transmissão "
                f"comprometida sugere impedimentos estruturais no setor bancário, incluindo "
                f"o legado de NPL, a aversão ao risco ou uma procura fraca de crédito."
            )
            strength = "impaired"
        elif ir_trend == "increasing" and credit_trend == "decreasing":
            narrative = (
                "A subida das taxas de juro está a travar a criação de crédito, consistente "
                "com a mecânica padrão da política monetária. O ciclo de aperto está a "
                "transmitir-se através das condições de crédito portuguesas, como pretendido."
            )
            strength = "strong"
        else:
            narrative = (
                f"A relação taxas de juro-crédito mostra padrões atípicos, com as taxas em "
                f"tendência {ir_trend} enquanto o crédito está em tendência {credit_trend}. "
                f"Podem estar em jogo fatores não convencionais, incluindo alterações "
                f"regulatórias, substituição pelos mercados de capitais ou mudanças "
                f"estruturais na procura de crédito."
            )
            strength = "atypical"
        relationships.append(
            {
                "name": "Transmissão da Política Monetária (Taxas-Crédito)",
                "pillars": ["interest_rates", "credit"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    # 3. Inflation-Monetary Policy Alignment
    inflation = summaries.get("inflation", {})
    if ir.get("status") == "ok" and inflation.get("status") == "ok":
        inf_latest = inflation.get("latest_value")
        ir_latest = ir.get("latest_value")
        if inf_latest is not None and ir_latest is not None:
            real_rate = ir_latest - inf_latest
            if inf_latest > 3 and ir_latest > inf_latest:
                narrative = (
                    f"A política monetária é restritiva: a taxa nominal ({s(ir_latest)}%) "
                    f"excede a inflação ({s(inf_latest)}%), gerando uma taxa real positiva de "
                    f"{s(real_rate)}%. Esta postura é apropriada para trazer a inflação de "
                    f"volta à meta de 2%, embora o impacto contracionista na atividade "
                    f"económica deva ser ponderado."
                )
            elif inf_latest > 3 and ir_latest < inf_latest:
                narrative = (
                    f"A política monetária pode ser insuficientemente restritiva: com a "
                    f"inflação em {s(inf_latest)}% e a taxa nominal em {s(ir_latest)}%, a taxa "
                    f"real é negativa ({s(real_rate)}%). Isto arrisca enraizar as expectativas "
                    f"inflacionistas e pode exigir novos aumentos de taxas."
                )
            elif inf_latest < 1 and ir_latest < 1:
                narrative = (
                    f"Tanto a inflação ({s(inf_latest)}%) como as taxas de juro "
                    f"({s(ir_latest)}%) estão em níveis historicamente baixos, refletindo um "
                    f"ambiente desinflacionista. A postura ultra-acomodatícia do BCE visa "
                    f"prevenir a deflação, mas tem margem limitada para mais flexibilização "
                    f"convencional."
                )
            else:
                narrative = (
                    f"A inflação em {s(inf_latest)}% e as taxas de juro em {s(ir_latest)}% "
                    f"sugerem uma postura monetária globalmente neutra, com uma taxa real de "
                    f"{s(real_rate)}%. A calibração parece apropriada dadas as condições "
                    f"atuais."
                )
            relationships.append(
                {
                    "name": "Alinhamento Inflação-Política Monetária",
                    "pillars": ["inflation", "interest_rates"],
                    "narrative": narrative,
                    "relationship_strength": "assessed",
                }
            )

    # 4. Debt Sustainability vs Growth Dynamics
    debt = summaries.get("public_debt", {})
    if gdp.get("status") == "ok" and debt.get("status") == "ok":
        gdp_growth_val = gdp.get("recent_avg_growth")
        debt_trend = debt.get("trend")
        debt_latest = debt.get("latest_value")
        primary_col = debt.get("primary_col", "")
        is_ratio = any(kw in primary_col.lower() for kw in ["ratio", "gdp", "percent"])

        if gdp_growth_val is not None and gdp_growth_val > 2 and debt_trend == "decreasing":
            narrative = (
                f"A dinâmica crescimento-dívida é favorável: um crescimento do PIB de "
                f"{s(gdp_growth_val)}% está a impulsionar uma trajetória descendente da "
                f"dívida (tendência: {debt_trend}). "
                f"{'Em ' + s(debt_latest) + '% do PIB, ' if is_ratio else ''}"
                f"o efeito de denominador do crescimento está a melhorar os rácios de "
                f"sustentabilidade. Este círculo virtuoso deve ser reforçado através de "
                f"reformas estruturais continuadas."
            )
            strength = "favourable"
        elif gdp_growth_val is not None and gdp_growth_val < 1 and debt_trend == "increasing":
            narrative = (
                f"Está a emergir um ciclo adverso preocupante: um crescimento fraco do PIB "
                f"({s(gdp_growth_val)}%) coincide com níveis crescentes de dívida. "
                f"{'Em ' + s(debt_latest) + '% do PIB, ' if is_ratio else ''}"
                f"a dinâmica dívida-crescimento arrisca tornar-se autorreforçada à medida que "
                f"o espaço orçamental se estreita e as opções de política anticíclica "
                f"diminuem."
            )
            strength = "adverse"
        else:
            narrative = (
                f"A relação crescimento-dívida está numa fase de transição. Um crescimento do "
                f"PIB de {s(gdp_growth_val)}% a par de uma trajetória {debt_trend} da dívida "
                f"sugere que a sustentabilidade depende criticamente da manutenção da atual "
                f"disciplina orçamental e da prevenção de choques de crescimento."
            )
            strength = "transitional"
        relationships.append(
            {
                "name": "Dinâmica Sustentabilidade da Dívida-Crescimento",
                "pillars": ["public_debt", "gdp"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    macro_narrative = synthesise_macro_narrative(summaries, relationships, db_path)

    return {
        "relationships": relationships,
        "macro_narrative": macro_narrative,
    }


def synthesise_macro_narrative(summaries: dict, relationships: list, db_path: str) -> str:
    """Build a data-driven macro narrative (Portuguese) structured as a 3-act story."""
    s = _safe
    parts = []

    with get_connection(db_path) as conn:

        def _q(sql):
            r = conn.execute(sql).fetchone()
            return r[0] if r else None

        latest_unemp = _q(
            "SELECT unemployment_rate FROM fact_unemployment f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        latest_debt = _q(
            "SELECT debt_to_gdp_ratio FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.quarter DESC LIMIT 1"
        )
        latest_deficit = _q(
            "SELECT budget_deficit_annual FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.quarter DESC LIMIT 1"
        )
        first_sub100_year = _q(
            "SELECT MIN(d.year) FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "WHERE d.quarter = 4 AND d.year > 2011 AND f.debt_to_gdp_ratio < 100"
        )
        latest_npl = _q(
            "SELECT npl_ratio FROM fact_credit f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "WHERE npl_ratio IS NOT NULL "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        latest_hicp = _q(
            "SELECT hicp FROM fact_inflation f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        # Picos limitados à janela 2010-2014 (Troika) para que o texto do Ato 1
        # seja literalmente verdadeiro: o pico histórico da dívida (137.5%) foi
        # o trimestre COVID de 2021, não a crise da dívida soberana (~134.7%
        # em 2014). O pico COVID é referido no Ato 3.
        peak_unemp = _q(
            "SELECT MAX(unemployment_rate) FROM fact_unemployment f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "WHERE d.year BETWEEN 2010 AND 2014"
        )
        peak_debt = _q(
            "SELECT MAX(debt_to_gdp_ratio) FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "WHERE d.year BETWEEN 2010 AND 2014"
        )
        covid_peak_debt = _q("SELECT MAX(debt_to_gdp_ratio) FROM fact_public_debt")

    # --- Ato 1: Crise e Ajustamento (2010-2014) ---
    parts.append(
        "ATO 1 — CRISE E AJUSTAMENTO (2010-2014): "
        "Portugal entrou na década sob severo stress macroeconómico. "
        f"O desemprego atingiu o pico de {s(peak_unemp)}%, "
        f"o rácio dívida/PIB subiu para {s(peak_debt)}%, "
        "e as yields das obrigações soberanas ultrapassaram os 10% à medida que os "
        "mercados incorporavam o risco de incumprimento. "
        "O programa de resgate da UE/FMI impôs uma consolidação orçamental que contraiu "
        "a economia mas lançou as bases para a reforma estrutural."
    )

    # --- Ato 2: Recuperação Orgânica (2015-2019) ---
    parts.append(
        "ATO 2 — RECUPERAÇÃO ORGÂNICA (2015-2019): "
        "Portugal alcançou uma combinação rara: descida do desemprego, "
        "queda dos rácios de dívida e um excedente orçamental em 2019 — o primeiro na "
        "história democrática portuguesa. O spread soberano normalizou para perto de zero, "
        "o sistema bancário iniciou a limpeza dos NPL, e o crescimento do PIB superou "
        "consistentemente a média da zona euro."
    )

    # --- Ato 3: Resiliência e Convergência (2020-2025) ---
    sub100_text = (
        f"abaixo da marca dos 100% desde {int(first_sub100_year)}"
        if first_sub100_year is not None
        else "novamente abaixo da marca dos 100%"
    )
    balance_word = "défice" if (latest_deficit is not None and latest_deficit < 0) else "excedente"
    balance_value = abs(latest_deficit) if latest_deficit is not None else None
    parts.append(
        "ATO 3 — RESILIÊNCIA E CONVERGÊNCIA (2020-2025): "
        "O choque da COVID causou uma contração acentuada mas temporária que elevou "
        f"a dívida/PIB a um máximo histórico de {s(covid_peak_debt)}% em 2021. "
        "A recuperação foi rápida: o PIB real ultrapassou os níveis pré-pandemia em 2022. "
        f"Em 2025, o desemprego situa-se em {s(latest_unemp)}% (perto da média da UE), "
        f"a dívida/PIB caiu para {s(latest_debt)}% ({sub100_text}), "
        f"e o saldo orçamental anual apresenta um {balance_word} de {s(balance_value)}% do PIB. "
        f"O rácio de NPL em {s(latest_npl)}% confirma um sistema bancário saneado."
    )

    # --- Riscos futuros ---
    risk_signals = []
    if latest_npl is not None and latest_npl < 3:
        risk_signals.append(
            "complacência no crédito (NPL em mínimos históricos pode mascarar riscos emergentes)"
        )
    if latest_hicp is not None and latest_hicp > 2.0:
        risk_signals.append(
            f"persistência da inflação ({s(latest_hicp)}% ainda acima da meta de 2% do BCE)"
        )
    risk_signals.append(
        "o défice de produtividade (o PIB per capita permanece em ~82% da média da UE "
        "em paridades de poder de compra)"
    )

    parts.append(
        "RISCOS FUTUROS: Apesar da melhoria estrutural, Portugal enfrenta "
        + ", ".join(risk_signals)
        + ". "
        "A era do crescimento fácil (recuperação da crise mais expansão nominal "
        "impulsionada pela inflação) está a terminar. O crescimento futuro terá de vir de "
        "ganhos de produtividade, e não de ventos cíclicos favoráveis."
    )

    # --- Implicação estratégica ---
    parts.append(
        "IMPLICAÇÃO ESTRATÉGICA: Portugal completou uma transformação fundamental, de "
        "beneficiário de resgate a membro orçamentalmente credível da zona euro. A "
        "prioridade de política deve agora deslocar-se da estabilização para a convergência "
        "sustentada — investindo o excedente orçamental em capital humano, digitalização e "
        "inovação, em vez de o consumir."
    )

    return "\n\n".join(parts)
