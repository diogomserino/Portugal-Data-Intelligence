"""
Portugal Data Intelligence — Pillar-Specific Rule-Based Insights (Portuguese)
=============================================================================
Portuguese mirror of ``pillar_insights.py``. The selection logic, thresholds
and data interpolation are identical to the English module, so the same data
picks the same narrative branch — only the prose is in Portuguese.

Each builder also returns an explicit ``risk_class`` token
(``low`` | ``moderate`` | ``elevated`` | ``high``) matching the colour the
English narrative would resolve to, so the HTML report renders the same risk
colour regardless of language.
"""

from typing import Dict, List, Optional, Tuple

from src.reporting.i18n import PILLAR_TITLES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TREND_PT = {"increasing": "crescente", "decreasing": "decrescente", "stable": "estável"}


def _trend_pt(trend: Optional[str]) -> str:
    return _TREND_PT.get(trend or "", trend or "estável")


# Crisis-period labels come from CRISIS_PERIODS (English); map them to Portuguese
# by the stable crisis key so the narratives don't leak English period names.
_CRISIS_LABELS_PT = {
    "sovereign_debt_crisis": "Crise da Dívida Soberana",
    "covid_pandemic": "Pandemia de COVID-19",
    "energy_crisis": "Crise Energética e da Inflação",
}


def _crisis_label(crisis_key: Optional[str], fallback: str) -> str:
    """Portuguese label for a crisis period, keyed by its stable key."""
    return _CRISIS_LABELS_PT.get(crisis_key or "", fallback)


def _safe(value, fmt: str = ".1f") -> str:
    """Format a numeric value safely, returning 'N/A' on failure."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):{fmt}}"
    except (TypeError, ValueError):
        return str(value)


def _classify_crisis_impact(mean_growth, longrun, mode: str = "growth") -> str:
    """Return a qualitative description of a crisis period's impact."""
    if mode == "growth":
        if mean_growth is not None and mean_growth < 0:
            return "stress económico significativo"
        if mean_growth is not None and longrun is not None:
            if mean_growth > longrun + 0.5:
                return "resiliência"
            if mean_growth < longrun - 0.5:
                return "stress significativo"
    elif mode == "level":
        if mean_growth is not None and longrun is not None:
            if mean_growth > longrun + 1:
                return "refletindo stress significativo"
            if mean_growth < longrun - 1:
                return "demonstrando resiliência"
    return "desempenho globalmente em linha com a tendência geral"


def _build_crisis_findings(d: dict, mode: str = "growth") -> List[str]:
    """Generate findings lines for each crisis period."""
    s = _safe
    longrun = d.get("longrun_avg_growth")
    findings = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        label = _crisis_label(_ck, ci["label"])
        if mode == "growth":
            mg = ci.get("mean_growth")
            impact = _classify_crisis_impact(mg, longrun, mode="growth")
            findings.append(
                f"Durante o período {label}, o crescimento médio foi de {s(mg)}%, "
                f"indicando {impact}."
            )
        else:
            mean_v = ci.get("mean_value")
            findings.append(f"O período {label} levou o indicador a uma média de {s(mean_v)}.")
    return findings


def _build_headline(
    value: Optional[float], thresholds: list, fmt_kwargs: dict, default: str
) -> str:
    """Select headline from threshold list and format with kwargs."""
    if value is None:
        return default
    for condition_fn, template in thresholds:
        if condition_fn(value):
            return template.format(**fmt_kwargs)
    return default


def _build_risk(
    value: float, recent: Optional[float], thresholds: list, fmt_kwargs: dict
) -> Tuple[str, str]:
    """Select risk assessment from threshold list. Returns (text, risk_class)."""
    for condition_fn, risk_class, template in thresholds:
        if condition_fn(value, recent):
            return template.format(**fmt_kwargs), risk_class
    return "RISCO MODERADO. É necessária análise adicional.", "moderate"


def _build_base_findings(d: dict) -> List[str]:
    """Generate the universal first 3 findings for any pillar."""
    s = _safe
    change = d["overall_change_pct"]
    return [
        f"{'Expansão' if change > 0 else 'Contração'} global de {s(abs(change))}% "
        f"de {d['earliest_year']} a {d['latest_year']}.",
        f"Máximo: {s(d['peak_value'])} em {d['peak_year']}; "
        f"Mínimo: {s(d['trough_value'])} em {d['trough_year']}.",
        f"Crescimento médio de longo prazo: {s(d.get('longrun_avg_growth'))}%; "
        f"média recente de 3 anos: {s(d.get('recent_avg_growth'))}%.",
    ]


def _build_momentum_paragraph(d: dict) -> str:
    """Build a paragraph comparing recent momentum to long-run average."""
    s = _safe
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")
    if recent is not None and longrun is not None:
        gap = recent - longrun
        if gap > 1:
            return (
                f"O momentum recente tem estado notavelmente acima da tendência, com a "
                f"taxa de crescimento média de três anos de {s(recent)}% a exceder a média "
                f"de longo prazo de {s(longrun)}% em {s(gap)} pontos percentuais. Esta "
                f"expansão acima da tendência deve ser avaliada quanto à sua sustentabilidade."
            )
        elif gap < -1:
            return (
                f"A média de crescimento recente de três anos de {s(recent)}% fica aquém da "
                f"média histórica de {s(longrun)}% em {s(abs(gap))} pontos percentuais, "
                f"indicando uma perda de momentum que pode exigir atenção de política."
            )
        else:
            return (
                f"O crescimento recente de {s(recent)}% está globalmente alinhado com a "
                f"média de longo prazo de {s(longrun)}%, sugerindo que a economia está a "
                f"operar perto da sua trajetória de crescimento potencial."
            )
    return (
        "Dados históricos insuficientes para avaliar o momentum recente face às "
        "tendências de longo prazo."
    )


def _build_crisis_narrative(d: dict, mode: str = "growth") -> str:
    """Build a paragraph summarising crisis period impacts."""
    s = _safe
    longrun = d.get("longrun_avg_growth")
    parts = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        label = _crisis_label(_ck, ci["label"])
        if mode == "growth":
            mg = ci.get("mean_growth")
            impact = _classify_crisis_impact(mg, longrun, mode="growth")
            parts.append(
                f"O período {label} registou um crescimento médio de {s(mg)}%, "
                f"indicando {impact}."
            )
        else:
            mean_v = ci.get("mean_value")
            max_v = ci.get("max_value")
            parts.append(
                f"Durante o {label}, o indicador teve uma média de {s(mean_v)} "
                f"e atingiu {s(max_v)} no seu pico."
            )
    if not parts:
        return (
            f"Ao longo de toda a janela de observação, a medida principal passou de "
            f"{s(d['earliest_value'])} para {s(d['latest_value'])}, uma variação "
            f"acumulada de {s(d['overall_change_pct'])}%."
        )
    return " ".join(parts)


def _add_secondary_findings(d: dict, findings: list, keywords_map: Dict[str, str]) -> List[str]:
    """Append findings from secondary columns based on keyword matching."""
    s = _safe
    for col_name, sec_data in d.get("secondary", {}).items():
        cl = col_name.lower()
        for keyword, template in keywords_map.items():
            if keyword in cl:
                findings.append(
                    template.format(
                        col=col_name,
                        mean=s(sec_data["mean"]),
                        latest=s(sec_data["latest"]),
                        min=s(sec_data["min"]),
                        max=s(sec_data["max"]),
                    )
                )
                break
    return findings[:6]


# ---------------------------------------------------------------------------
# Pillar configurations — thresholds and templates (PT)
# ---------------------------------------------------------------------------

_GDP_CONFIG = {
    "headline_thresholds": [
        (
            lambda g: g > 3,
            "Expansão económica robusta: o PIB de Portugal cresceu {growth}% em {year}",
        ),
        (lambda g: g > 1, "Crescimento moderado sustentado: o PIB avançou {growth}% em {year}"),
        (
            lambda g: g > 0,
            "Momentum de crescimento a esmorecer: o PIB expandiu apenas {growth}% em {year}",
        ),
        (lambda g: True, "Contração económica: o PIB recuou {growth}% em {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, r: v is not None and v < 0,
            "high",
            "RISCO ALTO. A economia contraiu {abs_growth}% em {year}. Trajetórias de "
            "crescimento negativo, se sustentadas, podem desencadear ciclos de retroação "
            "adversos através do emprego, das receitas fiscais e da qualidade do crédito. "
            "Justifica-se atenção de política imediata.",
        ),
        (
            lambda v, r: r is not None and r < 1,
            "elevated",
            "RISCO ELEVADO. O crescimento médio dos últimos três anos ({recent}%) está "
            "abaixo do limiar necessário para reduzir significativamente o desemprego ou "
            "estabilizar as finanças públicas. A economia está vulnerável a choques externos.",
        ),
        (
            lambda v, r: r is not None and r > 3,
            "elevated",
            "RISCO BAIXO com VIGILÂNCIA DE SOBREAQUECIMENTO. O forte crescimento recente "
            "({recent}%) pode gerar pressões inflacionistas ou desequilíbrios nos preços "
            "dos ativos. Monitorizar a utilização da capacidade e a tensão no mercado de "
            "trabalho.",
        ),
        (
            lambda v, r: True,
            "moderate",
            "RISCO MODERADO. O crescimento é positivo mas não suficientemente acima da "
            "tendência para fornecer uma proteção substancial contra cenários de descida. "
            "Recomenda-se vigilância sobre as condições da procura externa e os "
            "estrangulamentos estruturais.",
        ),
    ],
    "recommendations": {
        "low_growth": [
            "Acelerar a implementação do Plano de Recuperação e Resiliência (PRR) para "
            "impulsionar o investimento público e atrair capital privado.",
            "Considerar medidas de estímulo orçamental dirigidas a setores promotores da "
            "produtividade, incluindo a transformação digital e a transição verde.",
        ],
        "high_growth": [
            "Monitorizar os constrangimentos de capacidade e a escassez de mão de obra que "
            "possam estrangular o crescimento e empurrar a inflação acima da meta do BCE.",
        ],
        "always": [
            "Reforçar a diversificação das exportações para reduzir a dependência do "
            "turismo e dos ciclos da procura europeia.",
            "Priorizar o desenvolvimento do capital humano através do alinhamento da "
            "formação profissional com setores de elevado crescimento (tecnologia, "
            "energias renováveis, indústria avançada).",
        ],
    },
}

_UNEMPLOYMENT_CONFIG = {
    "headline_thresholds": [
        (lambda v: v < 7, "Robustez do mercado de trabalho: desemprego em {latest}% em {year}"),
        (
            lambda v: v < 10,
            "Condições moderadas no mercado de trabalho: desemprego em {latest}% em {year}",
        ),
        (lambda v: v < 14, "Desemprego elevado persiste em {latest}% em {year}"),
        (lambda v: True, "Desemprego crítico: taxa em {latest}% em {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 12,
            "high",
            "RISCO ALTO. O desemprego em {latest}% permanece criticamente elevado, gerando "
            "custos sociais significativos e restringindo a procura dos consumidores. A "
            "histerese do desemprego de longa duração é uma preocupação.",
        ),
        (
            lambda v, _r: v > 8,
            "elevated",
            "RISCO ELEVADO. Em {latest}%, o mercado de trabalho não normalizou totalmente. "
            "As componentes estruturais do desemprego podem resistir à recuperação cíclica, "
            "exigindo intervenção dirigida.",
        ),
        (
            lambda v, _r: True,
            "moderate",
            "RISCO MODERADO. O desemprego em {latest}% indica um mercado de trabalho "
            "saudável, ainda que a tensão possa gerar pressões salariais. Monitorizar "
            "lacunas de competências e desequilíbrios regionais que possam limitar "
            "melhorias adicionais.",
        ),
    ],
    "recommendations": {
        "always": [
            "Expandir os programas de formação profissional e requalificação alinhados com "
            "as exigências da economia digital e verde.",
            "Reforçar as políticas ativas do mercado de trabalho, em particular para os "
            "jovens e os desempregados de longa duração.",
            "Combater as disparidades regionais através de incentivos ao investimento nas "
            "regiões do interior com maior desemprego.",
        ],
        "high_unemployment": [
            "Considerar subsídios temporários ao emprego para os setores com maior "
            "potencial de criação de postos de trabalho.",
        ],
        "low_unemployment": [
            "Focar nas métricas de qualidade do emprego, incluindo tipos de contrato, "
            "crescimento salarial e produtividade por trabalhador, para assegurar "
            "resultados sustentáveis no mercado de trabalho.",
        ],
    },
}

_CREDIT_CONFIG = {
    "risk_thresholds": [
        (
            lambda t, r: t == "decreasing" and (r is None or r < 0),
            "high",
            "RISCO ALTO. A contração continuada do crédito sinaliza uma transmissão da "
            "política monetária comprometida e potencial racionamento do crédito. As "
            "pequenas e médias empresas podem enfrentar constrangimentos de financiamento "
            "que inibem o investimento e o crescimento.",
        ),
        (
            lambda t, r: t == "decreasing",
            "elevated",
            "RISCO ELEVADO. Embora o ritmo da quebra do crédito tenha moderado, a tendência "
            "globalmente contracionista indica necessidades persistentes de reparação dos "
            "balanços no setor bancário. A disponibilidade de crédito permanece um "
            "potencial estrangulamento.",
        ),
        (
            lambda t, r: True,
            "moderate",
            "RISCO MODERADO. As condições de crédito parecem estar a normalizar. O "
            "principal risco reside na qualidade do novo crédito e na adequação do "
            "crescimento do crédito para apoiar as necessidades de investimento da economia "
            "sem reconstruir uma alavancagem excessiva.",
        ),
    ],
    "recommendations": [
        "Monitorizar de perto as métricas de qualidade do crédito, assegurando que a "
        "expansão do crédito não compromete os critérios de concessão.",
        "Apoiar o acesso das PME ao financiamento através de programas de garantia e linhas "
        "de co-financiamento da banca de desenvolvimento.",
        "Incentivar a diversificação do financiamento das empresas para os mercados de "
        "capitais e plataformas de crédito alternativas.",
        "Avaliar a eficácia da transmissão da política monetária do BCE através dos canais "
        "bancários portugueses.",
    ],
}

_INTEREST_RATES_CONFIG = {
    "headline_thresholds": [
        (lambda v: v < 1, "Ambiente de taxas ultrabaixas: taxa diretora em {latest}% em {year}"),
        (lambda v: v < 3, "Normalização das taxas em curso: taxa diretora em {latest}% em {year}"),
        (lambda v: v > 5, "Ambiente de taxas elevadas: taxa diretora em {latest}% em {year}"),
        (lambda v: True, "Taxas de juro em {latest}%: condições monetárias a apertar em {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 4,
            "high",
            "RISCO ALTO. As taxas de juro elevadas em {latest}% colocam desafios "
            "significativos à capacidade de serviço da dívida de Portugal, aos detentores "
            "de crédito à habitação e ao investimento empresarial. O risco de stress "
            "financeiro nos setores sensíveis às taxas é material.",
        ),
        (
            lambda v, _r: v > 2,
            "elevated",
            "RISCO ELEVADO. A normalização das taxas para {latest}% cria pressões de "
            "ajustamento em toda a economia, em particular para os mutuários que acumularam "
            "dívida durante o período de taxas baixas. É essencial monitorizar os rácios de "
            "serviço da dívida das famílias e das empresas.",
        ),
        (
            lambda v, _r: v < 0.5,
            "moderate",
            "RISCO MODERADO (condições invulgares). As taxas próximas de zero em {latest}% "
            "apoiam os custos de financiamento mas sinalizam fraqueza económica subjacente. "
            "Os riscos incluem a má afetação de capital, a compressão das margens da banca "
            "e futuros custos de ajustamento quando as taxas finalmente normalizarem.",
        ),
        (
            lambda v, _r: True,
            "moderate",
            "RISCO MODERADO. A taxa atual de {latest}% representa um ambiente monetário de "
            "transição. Os principais riscos incluem o ritmo e a magnitude de futuros "
            "ajustamentos de taxas e o seu impacto diferenciado entre os setores económicos.",
        ),
    ],
    "recommendations": [
        "Realizar testes de stress às carteiras de dívida pública e privada face a novos "
        "aumentos de taxas de 100-200 pontos base.",
        "Incentivar produtos de crédito e empréstimo a taxa fixa para reduzir a exposição "
        "da economia à volatilidade das taxas.",
        "Monitorizar o spread soberano face aos referenciais da área do euro como indicador "
        "avançado da confiança dos mercados.",
        "Avaliar o impacto das variações de taxas na rentabilidade e na capacidade de "
        "concessão de crédito do setor bancário português.",
    ],
}

_INFLATION_CONFIG = {
    "headline_thresholds": [
        (lambda v: v > 5, "Surto inflacionista: taxa global em {latest}% em {year}"),
        (
            lambda v: v > 3,
            "Inflação acima da meta: taxa em {latest}% excede o objetivo de 2% do BCE em {year}",
        ),
        (
            lambda v: v > 1.5,
            "Inflação próxima da meta: taxa em {latest}% consistente com a estabilidade de preços em {year}",
        ),
        (lambda v: v > 0, "Ambiente de inflação baixa: taxa em {latest}% em {year}"),
        (lambda v: True, "Risco de deflação: inflação em {latest}% em {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 5,
            "high",
            "RISCO ALTO. A inflação em {latest}% está significativamente acima da meta de "
            "2% do BCE, erodindo o poder de compra e gerando incerteza para as decisões de "
            "investimento. Os efeitos de segunda ordem através de espirais preços-salários "
            "são uma preocupação material.",
        ),
        (
            lambda v, _r: v > 3,
            "elevated",
            "RISCO ELEVADO. A inflação acima da meta em {latest}% está a comprimir os "
            "rendimentos reais e pode levar a um maior aperto do BCE. A competitividade de "
            "Portugal pode ser afetada se a inflação doméstica exceder persistentemente a "
            "média da área do euro.",
        ),
        (
            lambda v, _r: v < 0.5,
            "elevated",
            "RISCO ELEVADO (deflação). Com a inflação em {latest}%, o risco de as "
            "expectativas deflacionistas se enraizarem não é negligenciável. A inflação "
            "baixa também aumenta o peso real da dívida, complicando a consolidação "
            "orçamental.",
        ),
        (
            lambda v, _r: True,
            "low",
            "RISCO BAIXO A MODERADO. A inflação em {latest}% é globalmente consistente com "
            "a estabilidade de preços. O principal risco é uma aceleração inesperada "
            "impulsionada pelos preços da energia, por disrupções nas cadeias de "
            "abastecimento ou por pressões salariais domésticas.",
        ),
    ],
    "recommendations": [
        "Monitorizar os padrões de fixação salarial em busca de sinais de efeitos de "
        "segunda ordem que possam enraizar a inflação acima da meta.",
        "Avaliar o impacto distributivo da inflação nas famílias de menores rendimentos e "
        "considerar medidas de apoio dirigidas.",
        "Avaliar a eficácia da transmissão da política monetária do BCE aos preços no "
        "consumidor portugueses.",
        "Acompanhar a divergência da inflação subjacente face à média da área do euro como "
        "indicador da dinâmica de competitividade.",
    ],
}

_PUBLIC_DEBT_CONFIG = {
    "risk_thresholds_ratio": [
        (
            lambda v, _r: v > 120,
            "high",
            "RISCO ALTO. A dívida em percentagem do PIB de {latest}% excede "
            "significativamente o limiar de 60% de Maastricht e a média da área do euro. "
            "Portugal permanece vulnerável a choques nas taxas de juro, a deceções no "
            "crescimento e a mudanças no sentimento dos mercados. Descidas de rating "
            "soberano poderiam desencadear ciclos de retroação adversos através dos "
            "balanços bancários.",
        ),
        (
            lambda v, _r: v > 90,
            "elevated",
            "RISCO ELEVADO. Em {latest}% do PIB, a dívida pública restringe o espaço da "
            "política orçamental e comporta risco de refinanciamento num ambiente de subida "
            "de taxas. A dinâmica dívida-crescimento-juros deve manter-se favorável para "
            "evitar uma espiral ascendente autorreforçada.",
        ),
        (
            lambda v, _r: v > 60,
            "moderate",
            "RISCO MODERADO. A dívida em {latest}% do PIB excede a referência de Maastricht "
            "mas situa-se numa trajetória gerível se a atual disciplina orçamental for "
            "mantida. O principal risco é um choque externo que reverta o progresso da "
            "consolidação.",
        ),
        (
            lambda v, _r: True,
            "moderate",
            "RISCO MODERADO. Os níveis de dívida pública situam-se dentro de limites "
            "geríveis. É necessária uma gestão orçamental prudente e continuada para manter "
            "esta posição e construir almofadas anticíclicas.",
        ),
    ],
    "recommendations": [
        "Manter excedentes orçamentais primários para assegurar uma trajetória descendente "
        "da dívida, visando um caminho da dívida em percentagem do PIB abaixo dos 100% no "
        "horizonte do quadro orçamental de médio prazo.",
        "Alargar a maturidade média das emissões de dívida pública para reduzir o risco de "
        "refinanciamento e fixar condições de financiamento favoráveis.",
        "Implementar revisões estruturais da despesa para identificar ganhos de eficiência "
        "que apoiem a consolidação sem comprometer o investimento público.",
        "Desenvolver planos orçamentais de contingência para cenários adversos (choque de "
        "crescimento, subida de taxas) para demonstrar preparação institucional aos "
        "mercados e às agências de rating.",
    ],
}


# ---------------------------------------------------------------------------
# GDP Insight
# ---------------------------------------------------------------------------


def _insight_gdp(d: dict) -> dict:
    s = _safe
    growth = d.get("latest_growth")
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")
    latest = d["latest_value"]

    fmt = {
        "growth": s(growth),
        "abs_growth": s(abs(growth)) if growth else "N/A",
        "recent": s(recent),
        "longrun": s(longrun),
        "latest": s(latest),
        "year": d["latest_year"],
    }

    headline = _build_headline(
        growth,
        _GDP_CONFIG["headline_thresholds"],
        fmt,
        default=f"Análise do PIB cobrindo {d['earliest_year']}-{d['latest_year']}",
    )

    if growth is not None and growth > 3:
        para1 = (
            f"A economia portuguesa demonstrou uma expansão robusta em {d['latest_year']}, "
            f"com o PIB a crescer {s(growth)}% em termos homólogos. Este ritmo superou a "
            f"média de longo prazo de {s(longrun)}%, sinalizando um momentum em fortalecimento."
        )
    elif growth is not None and growth > 1:
        para1 = (
            f"A economia portuguesa manteve um crescimento moderado em {d['latest_year']}, "
            f"registando uma expansão homóloga de {s(growth)}%, globalmente consistente com "
            f"o potencial de crescimento estrutural de Portugal e com a média de longo prazo "
            f"de {s(longrun)}%."
        )
    elif growth is not None and growth > 0:
        para1 = (
            f"O crescimento económico desacelerou em {d['latest_year']}, avançando apenas "
            f"{s(growth)}% em termos homólogos — um abrandamento notável face à média de "
            f"longo prazo de {s(longrun)}%."
        )
    elif growth is not None:
        para1 = (
            f"Portugal entrou numa fase de contração em {d['latest_year']}, com o PIB a "
            f"recuar {s(abs(growth))}% em termos homólogos, um desvio significativo face ao "
            f"crescimento médio de longo prazo de {s(longrun)}%."
        )
    else:
        para1 = (
            f"O conjunto de dados do PIB abrange {d['earliest_year']} a {d['latest_year']}, "
            f"cobrindo um período de evolução macroeconómica significativa para Portugal."
        )

    para2 = _build_crisis_narrative(d, mode="growth")
    para3 = _build_momentum_paragraph(d)

    findings = _build_base_findings(d) + _build_crisis_findings(d, mode="growth")
    findings = findings[:6]

    risk, risk_class = _build_risk(growth or 0, recent, _GDP_CONFIG["risk_thresholds"], fmt)

    recs = []
    if growth is not None and growth < 1:
        recs.extend(_GDP_CONFIG["recommendations"]["low_growth"])
    if recent is not None and recent > 3:
        recs.extend(_GDP_CONFIG["recommendations"]["high_growth"])
    recs.extend(_GDP_CONFIG["recommendations"]["always"])
    recs = recs[:4]

    if recent is not None and recent > 2:
        outlook = (
            f"A perspetiva de curto prazo é cautelosamente otimista. Com o crescimento "
            f"recente a rondar {s(recent)}%, a economia demonstrou resiliência. Contudo, a "
            f"convergência para a média da UE exige reformas estruturais sustentadas. Os "
            f"riscos externos, incluindo tensões comerciais globais e a volatilidade dos "
            f"preços da energia, permanecem fatores-chave."
        )
    elif recent is not None and recent > 0:
        outlook = (
            f"A trajetória de crescimento do PIB de Portugal deverá manter-se modesta. A "
            f"média recente de {s(recent)}% sugere margem limitada de manobra orçamental sem "
            f"reformas promotoras do crescimento. Existe potencial de subida através de "
            f"programas de investimento financiados pela UE e da força contínua do setor do "
            f"turismo."
        )
    else:
        outlook = (
            "A perspetiva económica comporta incerteza significativa. A recuperação "
            "dependerá da eficácia da política anticíclica e do ritmo de normalização da "
            "procura externa."
        )

    return {
        "pillar": "gdp",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Unemployment Insight
# ---------------------------------------------------------------------------


def _insight_unemployment(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"], "recent": s(d.get("recent_avg_growth"))}

    headline = _build_headline(
        latest,
        _UNEMPLOYMENT_CONFIG["headline_thresholds"],
        fmt,
        default=f"Desemprego em {s(latest)}% em {d['latest_year']}",
    )

    direction = (
        "diminuiu"
        if trend == "decreasing"
        else "aumentou" if trend == "increasing" else "manteve-se globalmente estável"
    )
    pp_change = abs(latest - d["earliest_value"])
    para1 = (
        f"O mercado de trabalho de Portugal passou por uma transformação significativa ao "
        f"longo de {d['earliest_year']}-{d['latest_year']}. A taxa de desemprego {direction} "
        f"de {s(d['earliest_value'])}% para {s(latest)}%, representando uma "
        f"{'melhoria' if change < 0 else 'deterioração'} de {s(pp_change)} pontos percentuais."
    )

    overall_mean = d.get("mean")
    crisis_text = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        max_v = ci.get("max_value")
        if mean_v is not None and overall_mean is not None and mean_v > overall_mean + 1:
            tone = "refletindo um stress significativo no mercado de trabalho"
        elif mean_v is not None and overall_mean is not None and mean_v < overall_mean - 1:
            tone = "demonstrando resiliência do mercado de trabalho"
        else:
            tone = "globalmente em linha com a tendência geral"
        crisis_text.append(
            f"Durante o {_crisis_label(_ck, ci['label'])}, o desemprego teve uma média de "
            f"{s(mean_v)}% e atingiu um pico de {s(max_v)}%, {tone}."
        )
    para2 = (
        " ".join(crisis_text)
        if crisis_text
        else (
            f"O desemprego atingiu o pico de {s(peak)}% em {peak_y} antes de descer para "
            f"{s(trough)}% em {trough_y}."
        )
    )

    if latest <= trough * 1.1:
        para3 = (
            f"A taxa atual de {s(latest)}% está próxima dos mínimos históricos, indicando "
            f"uma recuperação substancial do mercado de trabalho. Contudo, questões "
            f"estruturais, incluindo o desajustamento de competências e as disparidades "
            f"regionais, continuam a exigir atenção de política."
        )
    else:
        para3 = (
            f"Em {s(latest)}%, o desemprego permanece {s(latest - trough)} pontos "
            f"percentuais acima do mínimo do período de {s(trough)}% ({trough_y}). Melhorias "
            f"adicionais exigirão expansão económica continuada e políticas ativas dirigidas "
            f"do mercado de trabalho."
        )

    findings = [
        f"O desemprego {'caiu' if change < 0 else 'subiu'} {s(pp_change)} pontos "
        f"percentuais ao longo de todo o período.",
        f"Máximo: {s(peak)}% em {peak_y}; Mínimo: {s(trough)}% em {trough_y}.",
        f"Tendência geral classificada como {_trend_pt(trend)}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "youth": "O desemprego jovem teve uma média de {mean}%, leitura mais recente: "
            "{latest}% — evidenciando uma disparidade geracional persistente.",
        },
    )
    for _ck, ci in d.get("crisis_impacts", {}).items():
        findings.append(
            f"O {_crisis_label(_ck, ci['label'])} levou o desemprego a uma média de "
            f"{s(ci.get('mean_value'))}%."
        )
    findings = findings[:6]

    risk, risk_class = _build_risk(latest, None, _UNEMPLOYMENT_CONFIG["risk_thresholds"], fmt)

    recs = list(_UNEMPLOYMENT_CONFIG["recommendations"]["always"])
    if latest > 10:
        recs.extend(_UNEMPLOYMENT_CONFIG["recommendations"]["high_unemployment"])
    else:
        recs.extend(_UNEMPLOYMENT_CONFIG["recommendations"]["low_unemployment"])

    if trend == "decreasing" and latest < 8:
        outlook = (
            "A perspetiva do mercado de trabalho é positiva. Espera-se que a tendência "
            "descendente do desemprego prossiga, apoiada pelo crescimento económico e pela "
            "resiliência do setor do turismo. Contudo, as pressões demográficas e a "
            "emigração podem apertar a oferta de mão de obra."
        )
    elif trend == "decreasing":
        outlook = (
            "A trajetória descendente é encorajadora, ainda que a melhoria possa abrandar à "
            "medida que a economia se aproxima da sua taxa natural. O foco deve passar do "
            "volume de criação de emprego para a qualidade do emprego e o aumento da "
            "produtividade."
        )
    else:
        outlook = (
            "O mercado de trabalho enfrenta ventos contrários. Sem um crescimento sustentado "
            "do PIB acima de 2%, será difícil reduzir materialmente o desemprego. A "
            "coordenação de políticas entre educação, indústria e serviços de emprego será "
            "crítica."
        )

    return {
        "pillar": "unemployment",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Credit Insight
# ---------------------------------------------------------------------------


def _insight_credit(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")

    if trend == "decreasing":
        headline = (
            f"Contração do crédito: o financiamento recuou {s(abs(change))}% no período de análise"
        )
    elif recent is not None and recent > 3:
        headline = f"Expansão do crédito acelera: crescimento recente a rondar {s(recent)}% ao ano"
    else:
        headline = f"Condições de crédito estabilizam: saldo mais recente de {s(latest, '.0f')} milhões de euros"

    para1 = (
        f"O crédito à economia portuguesa exibiu uma trajetória {_trend_pt(trend)} ao longo "
        f"de {d['earliest_year']}-{d['latest_year']}. O crédito total em dívida passou de "
        f"{s(d['earliest_value'], '.0f')} para {s(latest, '.0f')} milhões de euros, uma "
        f"variação acumulada de {s(change)}%. Esta evolução reflete pressões de "
        f"desalavancagem na sequência da crise da dívida soberana, o aperto regulatório e a "
        f"subsequente normalização."
    )

    para2 = _build_crisis_narrative(d, mode="growth")

    if recent is not None and longrun is not None:
        if recent > longrun:
            para3 = (
                f"A dinâmica recente do crédito ({s(recent)}% de crescimento médio) mostra "
                f"melhoria face à média de longo prazo ({s(longrun)}%), sugerindo que o "
                f"ciclo de desalavancagem pode estar a aproximar-se do fim."
            )
        else:
            para3 = (
                f"Apesar das condições monetárias acomodatícias, o crescimento recente do "
                f"crédito ({s(recent)}%) permanece abaixo da média de longo prazo "
                f"({s(longrun)}%), indicando ventos contrários estruturais persistentes no "
                f"financiamento."
            )
    else:
        para3 = "Os dados do mercado de crédito sugerem uma normalização gradual das condições de financiamento."

    findings = _build_base_findings(d)
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "npl": "Indicador de NPL ({col}) teve uma média de {mean}%, mais recente: {latest}%.",
            "non_performing": "Indicador de NPL ({col}) teve uma média de {mean}%, mais recente: {latest}%.",
            "household": "Segmento '{col}' mais recente: {latest}, média: {mean}.",
            "nfc": "Segmento '{col}' mais recente: {latest}, média: {mean}.",
        },
    )

    risk, risk_class = _build_risk(
        trend, recent, _CREDIT_CONFIG["risk_thresholds"], {"latest": s(latest)}
    )

    recs = list(_CREDIT_CONFIG["recommendations"])

    if trend == "increasing" and recent is not None and recent > 3:
        outlook = (
            "Espera-se que as condições de crédito permaneçam favoráveis, com o crescimento "
            "do financiamento a moderar provavelmente para um ritmo sustentável à medida que "
            "o BCE ajusta a política monetária."
        )
    else:
        outlook = (
            "A perspetiva do crédito permanece cautelosa. Embora os fundamentais da banca "
            "tenham melhorado desde a crise da dívida soberana, desafios estruturais, "
            "incluindo as pressões de consolidação e os custos da transformação digital, "
            "podem limitar a capacidade de concessão de crédito."
        )

    return {
        "pillar": "credit",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Interest Rates Insight
# ---------------------------------------------------------------------------


def _insight_interest_rates(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"]}

    headline = _build_headline(
        latest,
        _INTEREST_RATES_CONFIG["headline_thresholds"],
        fmt,
        default=f"Taxas de juro em {s(latest)}% em {d['latest_year']}",
    )

    para1 = (
        f"O ambiente de taxas de juro em Portugal foi moldado por ciclos extraordinários de "
        f"política monetária ao longo de {d['earliest_year']}-{d['latest_year']}. A taxa "
        f"diretora passou de {s(d['earliest_value'])}% para {s(latest)}%, refletindo a "
        f"resposta do BCE a sucessivas crises e a subsequente normalização."
    )

    spread_text = ""
    for col_name, sec_data in d.get("secondary", {}).items():
        cl = col_name.lower()
        if any(kw in cl for kw in ("spread", "sovereign", "bond", "yield")):
            spread_text = (
                f" As yields soberanas portuguesas ({col_name}) tiveram uma média de "
                f"{s(sec_data['mean'])}%, mais recente em {s(sec_data['latest'])}%."
            )
            break

    if peak_y is not None and trough_y is not None and int(trough_y) < int(peak_y):
        para2 = (
            f"As taxas desceram para um mínimo de {s(trough)}% em {trough_y} sob as medidas "
            f"acomodatícias do BCE, e depois subiram para um pico de {s(peak)}% em {peak_y} à "
            f"medida que a política apertou contra a vaga de inflação pós-pandemia."
            f"{spread_text}"
        )
    else:
        para2 = (
            f"As taxas atingiram o pico de {s(peak)}% em {peak_y}, antes de descer para "
            f"{s(trough)}% em {trough_y} sob as medidas acomodatícias do BCE.{spread_text}"
        )

    para3 = (
        f"A taxa atual de {s(latest)}% deve ser avaliada no contexto do mandato de inflação "
        f"do BCE. Para Portugal, a transmissão às condições de crédito, aos custos do "
        f"crédito à habitação e ao serviço da dívida soberana exige monitorização cuidadosa."
    )

    findings = [
        f"A taxa diretora passou de {s(d['earliest_value'])}% para {s(latest)}% ao longo do período.",
        f"Máximo: {s(peak)}% em {peak_y}; Mínimo: {s(trough)}% em {trough_y}.",
        f"Tendência geral classificada como {_trend_pt(trend)}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "": "{col}: média {mean}%, intervalo [{min}% - {max}%], mais recente {latest}%.",
        },
    )

    risk, risk_class = _build_risk(latest, None, _INTEREST_RATES_CONFIG["risk_thresholds"], fmt)
    recs = list(_INTEREST_RATES_CONFIG["recommendations"])

    if trend == "increasing":
        outlook = (
            f"Espera-se que as taxas permaneçam influenciadas pelas decisões do BCE. Em "
            f"{s(latest)}%, a questão crítica é se Portugal consegue absorver custos de "
            f"financiamento mais elevados sem desencadear ciclos de retroação adversos "
            f"através do nexo soberano-banca-empresas."
        )
    else:
        outlook = (
            "O ambiente acomodatício pode persistir se a inflação se mantiver contida, mas a "
            "normalização da política representa um risco de ajustamento de médio prazo "
            "significativo. Portugal deve aproveitar esta janela para reduzir a dívida e "
            "reforçar as almofadas orçamentais."
        )

    return {
        "pillar": "interest_rates",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Inflation Insight
# ---------------------------------------------------------------------------


def _insight_inflation(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    mean_val = d["mean"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"]}

    headline = _build_headline(
        latest,
        _INFLATION_CONFIG["headline_thresholds"],
        fmt,
        default=f"Inflação em {s(latest)}% em {d['latest_year']}",
    )

    para1 = (
        f"A dinâmica da inflação em Portugal ao longo de {d['earliest_year']}-{d['latest_year']} "
        f"reflete a experiência europeia mais ampla. A inflação global teve uma média de "
        f"{s(mean_val)}% ao ano, passando de {s(d['earliest_value'])}% para {s(latest)}%. A "
        f"tendência é classificada como {_trend_pt(trend)}, com variação significativa "
        f"impulsionada por choques externos, preços da energia e transmissão da política "
        f"monetária."
    )

    crisis_parts = []
    for ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        label = _crisis_label(ck, ci["label"])
        if "energy" in ck.lower() or "covid" in ck.lower():
            crisis_parts.append(
                f"O {label} teve um impacto pronunciado nos preços, com a inflação a "
                f"registar uma média de {s(mean_v)}% durante o período."
            )
        else:
            crisis_parts.append(
                f"Durante o {label}, a inflação teve uma média de {s(mean_v)}%, "
                f"{'com as pressões desinflacionistas a dominar' if mean_v is not None and mean_v < 1 else 'refletindo fatores de custo'}."
            )
    para2 = (
        " ".join(crisis_parts)
        if crisis_parts
        else (
            f"A inflação atingiu o pico de {s(peak)}% em {peak_y} e atingiu {s(trough)}% em {trough_y}."
        )
    )

    core_text = ""
    for col_name, sec_data in d.get("secondary", {}).items():
        if "core" in col_name.lower():
            core_text = (
                f"A inflação subjacente (excluindo energia e alimentação) teve uma média de "
                f"{s(sec_data['mean'])}%, com uma leitura mais recente de "
                f"{s(sec_data['latest'])}%. A diferença entre as medidas global e subjacente "
                f"indica a persistência das pressões sobre os preços."
            )
            break
    para3 = core_text or (
        f"A taxa de inflação atual de {s(latest)}% deve ser avaliada face à meta de 2% do "
        f"BCE e à luz dos efeitos de segunda ordem das negociações salariais."
    )

    findings = [
        f"Inflação média: {s(mean_val)}% ao longo de todo o período.",
        f"Máximo: {s(peak)}% em {peak_y}; Mínimo: {s(trough)}% em {trough_y}.",
        f"Tendência classificada como {_trend_pt(trend)}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "core": "{col} teve uma média de {mean}%, mais recente: {latest}%.",
            "cpi_estimated": "{col} teve uma média de {mean}%, mais recente: {latest}%.",
        },
    )

    risk, risk_class = _build_risk(latest, None, _INFLATION_CONFIG["risk_thresholds"], fmt)
    recs = list(_INFLATION_CONFIG["recommendations"])

    if latest > 3:
        outlook = (
            "Espera-se que a inflação modere à medida que os efeitos de base da energia se "
            "dissipam e o aperto monetário se propaga pela economia. A inflação dos serviços "
            "e a dinâmica salarial no turismo serão determinantes-chave da trajetória de "
            "médio prazo."
        )
    elif latest < 1:
        outlook = (
            "A inflação baixa pode persistir se a procura se mantiver contida. Fatores "
            "estruturais, incluindo a globalização e a demografia, podem manter as pressões "
            "sobre os preços contidas."
        )
    else:
        outlook = (
            "A perspetiva da inflação é equilibrada. A inflação próxima da meta proporciona "
            "um ambiente estável para o planeamento. As principais incertezas são externas: "
            "mercados de energia, cadeias de abastecimento globais e calibração da política "
            "monetária do BCE."
        )

    return {
        "pillar": "inflation",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Public Debt Insight
# ---------------------------------------------------------------------------


def _insight_public_debt(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]
    primary_col = d.get("primary_col", "")

    is_ratio = any(kw in primary_col.lower() for kw in ("ratio", "gdp", "percent"))
    unit = "% do PIB" if is_ratio else "milhões de euros"
    vfmt = ".1f" if is_ratio else ".0f"

    if is_ratio:
        if latest > 120:
            headline = f"Preocupação de sustentabilidade da dívida: dívida pública em {s(latest)}% do PIB em {d['latest_year']}"
        elif latest > 100:
            headline = f"Dívida pública elevada: rácio em {s(latest)}% do PIB em {d['latest_year']}"
        elif latest > 60:
            headline = (
                f"Dívida acima do limiar de Maastricht: {s(latest)}% do PIB em {d['latest_year']}"
            )
        else:
            headline = (
                f"Dívida pública dentro do referencial: {s(latest)}% do PIB em {d['latest_year']}"
            )
    else:
        headline = f"Dívida pública em {s(latest, '.0f')} {unit} em {d['latest_year']}"

    para1 = (
        f"A trajetória da dívida pública de Portugal ao longo de {d['earliest_year']}-"
        f"{d['latest_year']} foi um desafio definidor do quadro macroeconómico. A medida "
        f"principal passou de {s(d['earliest_value'], vfmt)} para {s(latest, vfmt)} {unit}, "
        f"uma variação acumulada de {s(change)}%, moldada pela crise da dívida soberana, "
        f"pelos programas de austeridade e pela dinâmica de recuperação pós-crise."
    )

    crisis_parts = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        max_v = ci.get("max_value")
        crisis_parts.append(
            f"Durante o {_crisis_label(_ck, ci['label'])}, a dívida teve uma média de "
            f"{s(mean_v, vfmt)} {unit}, atingindo {s(max_v, vfmt)} no seu pico."
        )
    para2 = (
        " ".join(crisis_parts)
        if crisis_parts
        else (
            f"A dívida atingiu o pico de {s(peak, vfmt)} {unit} em {peak_y}, antes de "
            f"{'descer' if trend == 'decreasing' else 'estabilizar'} para o nível atual."
        )
    )

    trend_narratives = {
        "decreasing": (
            f"A tendência descendente da dívida é um sinal positivo. Contudo, em "
            f"{s(latest, vfmt)} {unit}, Portugal permanece acima da média da área do euro e "
            f"do limiar de 60% de Maastricht. É essencial manter a disciplina orçamental."
        ),
        "increasing": (
            f"A trajetória ascendente levanta preocupações de sustentabilidade. Em "
            f"{s(latest, vfmt)} {unit}, o espaço orçamental está limitado. Planos credíveis "
            f"de consolidação de médio prazo são críticos para a confiança dos mercados."
        ),
    }
    para3 = trend_narratives.get(
        trend,
        (
            f"A estabilização da dívida em torno de {s(latest, vfmt)} {unit} representa uma "
            f"fase de transição. O caminho a seguir depende da geração de excedentes "
            f"primários, do crescimento do PIB nominal e da taxa de juro efetiva da dívida "
            f"em circulação."
        ),
    )

    findings = [
        f"A dívida pública {'aumentou' if change > 0 else 'diminuiu'} {s(abs(change))}% ao "
        f"longo de todo o período.",
        f"Máximo: {s(peak, vfmt)} {unit} em {peak_y}; Mínimo: {s(trough, vfmt)} em {trough_y}.",
        f"Tendência da dívida classificada como {_trend_pt(trend)}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "balance": "Saldo orçamental ({col}): média {mean}, mais recente {latest}.",
            "deficit": "Saldo orçamental ({col}): média {mean}, mais recente {latest}.",
        },
    )

    fmt = {"latest": s(latest), "year": d["latest_year"]}
    if is_ratio:
        risk, risk_class = _build_risk(
            latest, None, _PUBLIC_DEBT_CONFIG["risk_thresholds_ratio"], fmt
        )
    else:
        risk = (
            f"RISCO MODERADO. A dívida pública em {s(latest, '.0f')} {unit} exige "
            f"monitorização contínua."
        )
        risk_class = "moderate"

    recs = list(_PUBLIC_DEBT_CONFIG["recommendations"])

    if trend == "decreasing":
        outlook = (
            "A perspetiva orçamental é cautelosamente positiva. Uma trajetória descendente "
            "sustentada da dívida posiciona Portugal para potenciais subidas de rating de "
            "crédito. Pressupostos-chave: crescimento do PIB acima de 1,5%, excedentes "
            "primários e condições de financiamento estáveis."
        )
    else:
        outlook = (
            "A perspetiva orçamental comporta riscos materiais. Sem uma consolidação "
            "credível, a dinâmica da dívida pode deteriorar-se, em particular se as taxas "
            "permanecerem elevadas. As pressões demográficas sobre a despesa em pensões e "
            "saúde intensificar-se-ão."
        )

    return {
        "pillar": "public_debt",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "risk_class": risk_class,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def _insight_generic_pt(d: dict) -> dict:
    s = _safe
    pillar = d.get("pillar", "unknown")
    pillar_name = PILLAR_TITLES["pt"].get(pillar, pillar.replace("_", " ").title())
    return {
        "pillar": pillar,
        "headline": f"{pillar_name}: último valor {s(d.get('latest_value'))} em {d.get('latest_year')}",
        "executive_summary": (
            f"A análise do pilar {pillar_name} abrange "
            f"{d.get('earliest_year')}-{d.get('latest_year')}. A tendência geral é "
            f"classificada como {_trend_pt(d.get('trend'))}. A medida principal passou de "
            f"{s(d.get('earliest_value'))} para {s(d.get('latest_value'))}, representando "
            f"uma variação acumulada de {s(d.get('overall_change_pct'))}%."
        ),
        "key_findings": [
            f"Variação global: {s(d.get('overall_change_pct'))}%.",
            f"Máximo: {s(d.get('peak_value'))} em {d.get('peak_year')}.",
            f"Mínimo: {s(d.get('trough_value'))} em {d.get('trough_year')}.",
        ],
        "risk_assessment": f"RISCO MODERADO. É necessária análise adicional para o pilar {pillar_name}.",
        "risk_class": "moderate",
        "recommendations": [
            f"Realizar uma análise mais aprofundada dos determinantes e fatores estruturais de {pillar_name}.",
        ],
        "outlook": f"A perspetiva para {pillar_name} depende de desenvolvimentos de política a nível doméstico e europeu.",
    }


# ---------------------------------------------------------------------------
# Dispatch dictionary mapping pillar names to their insight functions
# ---------------------------------------------------------------------------
PILLAR_DISPATCH_PT = {
    "gdp": _insight_gdp,
    "unemployment": _insight_unemployment,
    "credit": _insight_credit,
    "interest_rates": _insight_interest_rates,
    "inflation": _insight_inflation,
    "public_debt": _insight_public_debt,
}
