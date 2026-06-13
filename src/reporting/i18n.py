"""
Portugal Data Intelligence — Report Internationalisation (i18n)
================================================================
Single source of truth for all *static* report text in both English
("en") and Portuguese ("pt").

Three tables are exported:

* ``STRINGS``        — the report "chrome" (section titles, labels, captions,
                       intros, table headers, methodology / platform prose).
* ``COLUMN_LABELS``  — human-readable indicator labels (used by HTML tables and
                       Plotly axis titles).
* ``PILLAR_TITLES``  — the per-pillar section headings.

The dynamic narrative text (headlines, executive summaries, risk assessments,
…) is *not* here — it is produced per-language by the insight engine and read
from the executive-briefing JSON.

Usage::

    from src.reporting.i18n import tr, COLUMN_LABELS, PILLAR_TITLES
    S = tr(lang)                       # dict for the chosen language (en/pt)
    label = S["kpi_section_title"]
    col = COLUMN_LABELS[lang].get("hicp")
"""

from typing import Dict

SUPPORTED_LANGS = ("en", "pt")
DEFAULT_LANG = "en"

# Display name of each language (used by the language switch UI).
LANG_NAMES = {"en": "EN", "pt": "PT"}
LANG_FULL = {"en": "English", "pt": "Português"}


# ===========================================================================
# COLUMN LABELS — indicator names for tables and chart axes
# ===========================================================================

COLUMN_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "nominal_gdp": "Nominal GDP (EUR M)",
        "real_gdp": "Real GDP (EUR M)",
        "gdp_growth_yoy": "GDP Growth YoY (%)",
        "gdp_growth_qoq": "GDP Growth QoQ (%)",
        "gdp_per_capita": "GDP per Capita (EUR)",
        "unemployment_rate": "Unemployment Rate (%)",
        "youth_unemployment_rate": "Youth Unemployment (%)",
        "long_term_unemployment_rate": "Long-term Unemp. (%)",
        "labour_force_participation_rate": "Labour Force Part. (%)",
        "total_credit": "Total Credit (EUR M)",
        "credit_nfc": "Credit to NFCs (EUR M)",
        "credit_households": "Household Credit (EUR M)",
        "npl_ratio": "NPL Ratio (%)",
        "ecb_main_refinancing_rate": "ECB Main Rate (%)",
        "euribor_3m": "Euribor 3M (%)",
        "euribor_6m": "Euribor 6M (%)",
        "euribor_12m": "Euribor 12M (%)",
        "portugal_10y_bond_yield": "PT 10Y Bond Yield (%)",
        "hicp": "HICP Inflation (%)",
        "cpi_estimated": "CPI Estimated (%)",
        "core_inflation": "Core Inflation (%)",
        "total_debt": "Total Debt (EUR M)",
        "debt_to_gdp_ratio": "Debt-to-GDP Ratio (%)",
        "budget_deficit": "Budget Balance Quarterly (% GDP)",
        "budget_deficit_annual": "Budget Balance Annual (% GDP)",
        "external_debt_share_estimated": "External Debt Share Est. (%)",
        "house_price_index": "House Price Index (2015=100)",
        "house_price_yoy_change": "House Price Growth YoY (%)",
        "avg_price_per_sqm": "Avg. Price per sqm (EUR)",
        "housing_transactions": "Housing Transactions",
        "mortgage_new_loans": "New Mortgage Loans (EUR M)",
        "employment_services_pct": "Employment: Services (%)",
        "employment_industry_pct": "Employment: Industry (%)",
        "employment_agriculture_pct": "Employment: Agriculture (%)",
        "real_wage_index": "Real Wage Index (2015=100)",
        "labour_productivity_index": "Labour Productivity Index (2015=100)",
        "trade_balance_pct_gdp": "Trade Balance (% GDP)",
        "current_account_pct_gdp": "Current Account (% GDP)",
        "reer_index": "REER Index (2015=100)",
        "export_growth_yoy": "Export Growth YoY (%)",
        "total_revenue_pct_gdp": "Total Revenue (% GDP)",
        "total_expenditure_pct_gdp": "Total Expenditure (% GDP)",
        "health_expenditure_pct": "Health Expenditure (% GDP)",
        "education_expenditure_pct": "Education Expenditure (% GDP)",
        "social_protection_pct": "Social Protection (% GDP)",
        "interest_payments_pct": "Interest Payments (% GDP)",
        "gini_index": "Gini Index",
        "s80_s20_ratio": "S80/S20 Income Ratio",
        "poverty_risk_rate": "Poverty Risk Rate (%)",
        "median_income_index": "Median Income Index (EU27=100)",
    },
    "pt": {
        "nominal_gdp": "PIB Nominal (M€)",
        "real_gdp": "PIB Real (M€)",
        "gdp_growth_yoy": "Crescimento do PIB Homólogo (%)",
        "gdp_growth_qoq": "Crescimento do PIB Trimestral (%)",
        "gdp_per_capita": "PIB per Capita (€)",
        "unemployment_rate": "Taxa de Desemprego (%)",
        "youth_unemployment_rate": "Desemprego Jovem (%)",
        "long_term_unemployment_rate": "Desemprego Longa Duração (%)",
        "labour_force_participation_rate": "Taxa de Atividade (%)",
        "total_credit": "Crédito Total (M€)",
        "credit_nfc": "Crédito a Empresas (M€)",
        "credit_households": "Crédito a Particulares (M€)",
        "npl_ratio": "Rácio de NPL (%)",
        "ecb_main_refinancing_rate": "Taxa Diretora BCE (%)",
        "euribor_3m": "Euribor 3M (%)",
        "euribor_6m": "Euribor 6M (%)",
        "euribor_12m": "Euribor 12M (%)",
        "portugal_10y_bond_yield": "Yield OT Portuguesas 10A (%)",
        "hicp": "Inflação IHPC (%)",
        "cpi_estimated": "IPC Estimado (%)",
        "core_inflation": "Inflação Subjacente (%)",
        "total_debt": "Dívida Total (M€)",
        "debt_to_gdp_ratio": "Rácio Dívida/PIB (%)",
        "budget_deficit": "Saldo Orçamental Trimestral (% PIB)",
        "budget_deficit_annual": "Saldo Orçamental Anual (% PIB)",
        "external_debt_share_estimated": "Peso da Dívida Externa Est. (%)",
        "house_price_index": "Índice de Preços da Habitação (2015=100)",
        "house_price_yoy_change": "Crescimento dos Preços da Habitação Homólogo (%)",
        "avg_price_per_sqm": "Preço Médio por m² (€)",
        "housing_transactions": "Transações de Habitação",
        "mortgage_new_loans": "Novo Crédito à Habitação (M€)",
        "employment_services_pct": "Emprego: Serviços (%)",
        "employment_industry_pct": "Emprego: Indústria (%)",
        "employment_agriculture_pct": "Emprego: Agricultura (%)",
        "real_wage_index": "Índice de Salários Reais (2015=100)",
        "labour_productivity_index": "Índice de Produtividade do Trabalho (2015=100)",
        "trade_balance_pct_gdp": "Balança Comercial (% PIB)",
        "current_account_pct_gdp": "Balança Corrente (% PIB)",
        "reer_index": "Índice TCER (2015=100)",
        "export_growth_yoy": "Crescimento das Exportações Homólogo (%)",
        "total_revenue_pct_gdp": "Receita Total (% PIB)",
        "total_expenditure_pct_gdp": "Despesa Total (% PIB)",
        "health_expenditure_pct": "Despesa em Saúde (% PIB)",
        "education_expenditure_pct": "Despesa em Educação (% PIB)",
        "social_protection_pct": "Proteção Social (% PIB)",
        "interest_payments_pct": "Juros da Dívida (% PIB)",
        "gini_index": "Índice de Gini",
        "s80_s20_ratio": "Rácio de Rendimento S80/S20",
        "poverty_risk_rate": "Taxa de Risco de Pobreza (%)",
        "median_income_index": "Índice de Rendimento Mediano (EU27=100)",
    },
}


# ===========================================================================
# PILLAR TITLES — per-pillar section headings
# ===========================================================================

PILLAR_TITLES: Dict[str, Dict[str, str]] = {
    "en": {
        "gdp": "Gross Domestic Product",
        "unemployment": "Labour Market & Employment",
        "credit": "Credit to the Economy",
        "interest_rates": "Interest Rate Environment",
        "inflation": "Price Stability & Inflation",
        "public_debt": "Public Debt Sustainability",
        "housing": "Housing Market",
        "labor_detail": "Labour Market Detail",
        "external_accounts": "External Competitiveness",
        "fiscal": "Fiscal Structure",
        "inequality": "Inequality & Income",
    },
    "pt": {
        "gdp": "Produto Interno Bruto",
        "unemployment": "Mercado de Trabalho e Emprego",
        "credit": "Crédito à Economia",
        "interest_rates": "Ambiente de Taxas de Juro",
        "inflation": "Estabilidade de Preços e Inflação",
        "public_debt": "Sustentabilidade da Dívida Pública",
        "housing": "Mercado Imobiliário",
        "labor_detail": "Detalhe do Mercado de Trabalho",
        "external_accounts": "Competitividade Externa",
        "fiscal": "Estrutura Orçamental",
        "inequality": "Desigualdade e Rendimento",
    },
}


# ===========================================================================
# FORECAST INDICATOR NAMES — the forecaster emits English; localise by pillar
# ===========================================================================

FORECAST_INDICATORS: Dict[str, Dict[str, str]] = {
    "en": {
        "gdp": "Real GDP (EUR millions)",
        "unemployment": "Unemployment rate (%)",
        "inflation": "HICP inflation (%)",
        "interest_rates": "Interest Rates",
        "credit": "Total Credit (EUR millions)",
        "public_debt": "Debt-to-GDP ratio (%)",
    },
    "pt": {
        "gdp": "PIB Real (M€)",
        "unemployment": "Taxa de Desemprego (%)",
        "inflation": "Inflação IHPC (%)",
        "interest_rates": "Taxas de Juro",
        "credit": "Crédito Total (M€)",
        "public_debt": "Rácio Dívida/PIB (%)",
    },
}


# ===========================================================================
# RISK-LEVEL DISPLAY LABELS — keyed by neutral class token
# ===========================================================================

RISK_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "low": "LOW",
        "moderate": "MODERATE",
        "elevated": "ELEVATED",
        "high": "HIGH",
        "unknown": "UNKNOWN",
    },
    "pt": {
        "low": "BAIXO",
        "moderate": "MODERADO",
        "elevated": "ELEVADO",
        "high": "ALTO",
        "unknown": "DESCONHECIDO",
    },
}


# ===========================================================================
# STRINGS — the report "chrome"
# ===========================================================================

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "html_title": "Portugal Macroeconomic Intelligence Briefing",
        "default_briefing_title": "Portugal Macroeconomic Intelligence Briefing",
        # Cover
        "kicker": "Economic Research &middot; Portugal Data Intelligence",
        "dek": "A structural read of the Portuguese economy across twelve "
        "macroeconomic pillars, {start}&ndash;{end}.",
        "edition": "Edition v{version}",
        "exec_summary_label": "Executive summary",
        "ticker_gdp": "GDP",
        "ticker_unemployment": "Unemployment",
        "ticker_inflation": "Inflation",
        "ticker_debt": "Debt/GDP",
        "ticker_yield": "10Y Yield",
        # Contents / navigation
        "contents": "Contents",
        # KPI dashboard
        "kpi_section_title": "Key Indicators &mdash; Latest Values",
        "kpi_gdp_growth": "GDP Growth",
        "kpi_unemployment": "Unemployment",
        "kpi_inflation": "Inflation (HICP)",
        "kpi_debt": "Debt / GDP",
        "kpi_yield": "10Y Bond Yield",
        "kpi_npl": "NPL Ratio",
        "kpi_vs_prev": "vs prev",
        # Generic section labels
        "key_findings": "Key Findings",
        "descriptive_statistics": "Descriptive Statistics ({start}&ndash;{end})",
        "risk_assessment": "Risk Assessment:",
        "outlook": "Outlook",
        "source": "Source",
        "interactive_note": "interactive: zoom, hover, download",
        # Stats table headers
        "th_indicator": "Indicator",
        "th_mean": "Mean",
        "th_std": "Std Dev",
        "th_median": "Median",
        # TOC labels (non-pillar)
        "toc_key_indicators": "Key Indicators",
        "toc_executive_dashboard": "Executive Dashboard",
        "toc_cross_pillar": "Cross-Pillar Analysis",
        "toc_stl": "STL Decomposition",
        "toc_forecasting": "SARIMAX Forecasting",
        "toc_benchmarking": "EU Benchmarking",
        "toc_regional": "Regional Analysis (NUTS2)",
        "toc_risk_matrix": "Risk Matrix",
        "toc_recommendations": "Strategic Recommendations",
        "toc_platform": "Platform &amp; Tools",
        "toc_methodology": "Methodology",
        # Cross-pillar
        "cross_pillar_title": "Cross-Pillar Analysis",
        "cap_correlation": "Cross-pillar correlation matrix",
        "cap_phillips": "Phillips curve: unemployment vs inflation",
        "cap_crisis": "Crisis timeline: macroeconomic stress periods",
        # Benchmarking
        "benchmarking_title": "EU Benchmarking",
        "benchmarking_intro": "Portugal's macroeconomic performance compared to key "
        "European peers (Germany, Spain, France, Italy) and EU/Euro Area averages.",
        "cap_radar": "Portugal vs EU averages — normalised radar",
        "cap_small_multiples": "Peer country comparison — key indicators",
        # Regional
        "regional_title": "Regional Analysis — NUTS2",
        "regional_intro": "Portugal's macroeconomic performance varies significantly "
        "across its seven NUTS2 regions. Lisboa accounts for a disproportionate share "
        "of national GDP while peripheral regions face structural challenges in "
        "competitiveness and employment.",
        "regional_th_code": "Code",
        "regional_th_region": "Region",
        "regional_th_gdp": "GDP per Capita (PPS)",
        "regional_th_unemp": "Unemployment",
        "regional_map_title": "GDP per capita by NUTS2 region (PPS), latest year",
        "regional_map_note": "interactive choropleth — hover over each region",
        "regional_source": "Eurostat (nama_10r_2gdp)",
        "regional_synthetic_note": "Note: data based on synthetic estimates — run "
        "<code>python main.py</code> to populate live data.",
        # Executive dashboard
        "exec_dashboard_title": "Executive Dashboard",
        "exec_dashboard_intro": "Single-view summary of all six macroeconomic pillars — "
        "GDP, unemployment, credit, interest rates, inflation, and public debt — "
        "spanning {start} to {end}.",
        "exec_dashboard_caption": "Six core pillars at a glance, {start}&ndash;{end}",
        # STL
        "stl_title": "Seasonal-Trend Decomposition (STL)",
        "stl_intro": "Decomposition of key economic time series into trend, seasonal, "
        "and residual components using STL (Seasonal and Trend decomposition using "
        "Loess). This reveals underlying structural trends stripped of seasonal noise.",
        "cap_stl_gdp": "STL decomposition: real GDP",
        "cap_stl_unemployment": "STL decomposition: unemployment rate",
        "cap_stl_inflation": "STL decomposition: HICP inflation",
        # Forecasting
        "forecasting_title": "SARIMAX Forecasting",
        "forecasting_intro": "12-quarter-ahead forecasts generated by SARIMAX models "
        "with automatic order selection via AIC. Models are cached for 7 days (joblib) "
        "and refit when new data arrives. Shaded bands show 68% and 95% prediction "
        "intervals; residual diagnostics include the Ljung-Box test.",
        "fc_th_indicator": "Indicator",
        "fc_th_latest_period": "Latest Period",
        "fc_th_latest_value": "Latest Value",
        "fc_th_horizon": "Horizon",
        "fc_th_forecast": "Forecast",
        "fc_th_direction": "Direction",
        "fc_historical": "Historical",
        "fc_forecast_name": "{method} Forecast",
        "fc_chart_title": "{indicator} — 12-quarter forecast",
        "fc_source": "Portugal Data Intelligence model suite",
        "fc_note": "method: {method}; shaded bands are 68% / 95% intervals",
        # Risk matrix
        "risk_matrix_title": "Risk Matrix",
        "rm_th_pillar": "Pillar",
        "rm_th_level": "Risk Level",
        "rm_th_assessment": "Assessment",
        # Recommendations
        "recommendations_title": "Strategic Recommendations",
        # Platform
        "platform_title": "Platform &amp; Tools",
        "platform_intro": "Portugal Data Intelligence v{version} delivers insights "
        "through multiple complementary channels, each tailored to a different audience "
        "and use case.",
        "platform_dashboard_h": "Interactive Dashboard (Streamlit)",
        "platform_dashboard_p": "Four-page web dashboard with real-time KPI cards, "
        "per-pillar deep-dive with configurable year range and indicator filters, "
        "cross-pillar correlation heatmap with Phillips curve analysis, and a raw data "
        "explorer with CSV download.",
        "platform_api_h": "REST API (FastAPI)",
        "platform_api_p": "Seven endpoints exposing macroeconomic data "
        "programmatically: pillar listing, latest values with summary statistics, "
        "filtered timeseries queries, active alert monitoring, and cross-pillar "
        "correlation matrices. Full OpenAPI documentation at <code>/docs</code>.",
        "platform_forecast_h": "Ensemble Forecasting",
        "platform_forecast_p": "Multi-model forecasting combining SARIMAX, "
        "Holt-Winters, linear trend, mean-reversion, and log-linear models. Models are "
        "automatically weighted by inverse MAE from expanding-window backtesting, "
        "producing robust consensus projections with 68% and 95% confidence bands.",
        "platform_powerbi_h": "Power BI Dashboard",
        "platform_powerbi_p": "39 DAX measures across 7 categories (KPIs, YoY growth, "
        "moving averages, derived metrics, period comparisons, formatting, calculated "
        "columns) for enterprise-grade interactive dashboards with drill-down and "
        "what-if analysis.",
        "platform_footnote": "Additionally, the platform includes a configurable "
        "<strong>alert engine</strong> with warning/critical thresholds for 11 "
        "indicators across the economic pillars, an <strong>API response cache</strong> "
        "to reduce redundant HTTP calls to Eurostat, ECB, and Banco de Portugal, and a "
        "comprehensive <strong>CI/CD pipeline</strong> (GitHub Actions) with linting, "
        "testing across Python 3.10&ndash;3.12, and automated coverage reporting.",
        "launch": "Launch:",
        # Methodology
        "methodology_title": "Methodology &amp; Data Sources",
        "methodology_intro": "This report analyses the Portuguese economy across twelve "
        "macroeconomic pillars plus regional NUTS2 analysis, using data from {start} to "
        "{end}. The core macro-financial pillars (GDP, unemployment, inflation, interest "
        "rates, credit, public debt) and the inequality and regional series carry the "
        "official values published by the institutions below. The housing, "
        "labour-structure, external-accounts and fiscal pillars are modelled series "
        "calibrated to the corresponding official releases (Eurostat, INE, Banco de "
        "Portugal); they track the published levels and dynamics but are not the raw "
        "official records.",
        "methodology_th_source": "Source",
        "methodology_th_url": "URL",
        "methodology_granularity": "<strong>Granularity:</strong> GDP, Public Debt, and "
        "External Accounts are quarterly; Unemployment, Credit, Interest Rates, and "
        "Inflation are monthly; Housing, Labour Detail, Fiscal, Inequality, and Regional "
        "are annual.",
        "methodology_quality": "<strong>Data Quality:</strong> All pillars pass an "
        "8-check validation framework (schema, nulls, ranges, outliers, drift, "
        "completeness, consistency, freshness).",
        "methodology_engine": "<strong>Analysis Engine:</strong> Python (pandas, "
        "statsmodels, scipy) with SQLite storage, ensemble forecasting, and automated "
        "reporting.",
        "methodology_delivery": "<strong>Delivery:</strong> Power BI, Streamlit "
        "dashboard, self-contained HTML, REST API (FastAPI).",
        "methodology_version": "<strong>Version:</strong> {version} &mdash; Generated " "{date}",
        # Footer
        "footer_author_line": "Portugal Data Intelligence v{version}",
        "footer_tagline": "Diogo Serino &middot; Portfolio 2026 &middot; Power BI "
        "&middot; Streamlit &middot; FastAPI &middot; HTML",
        "footer_generated": "Report generated: {generated}",
        # Language switch
        "lang_switch_label": "Language",
    },
    "pt": {
        "html_title": "Briefing de Inteligência Macroeconómica de Portugal",
        "default_briefing_title": "Briefing de Inteligência Macroeconómica de Portugal",
        # Cover
        "kicker": "Investigação Económica &middot; Portugal Data Intelligence",
        "dek": "Uma leitura estrutural da economia portuguesa ao longo de doze "
        "pilares macroeconómicos, {start}&ndash;{end}.",
        "edition": "Edição v{version}",
        "exec_summary_label": "Sumário executivo",
        "ticker_gdp": "PIB",
        "ticker_unemployment": "Desemprego",
        "ticker_inflation": "Inflação",
        "ticker_debt": "Dívida/PIB",
        "ticker_yield": "Yield 10A",
        # Contents / navigation
        "contents": "Índice",
        # KPI dashboard
        "kpi_section_title": "Indicadores-Chave &mdash; Últimos Valores",
        "kpi_gdp_growth": "Crescimento do PIB",
        "kpi_unemployment": "Desemprego",
        "kpi_inflation": "Inflação (IHPC)",
        "kpi_debt": "Dívida / PIB",
        "kpi_yield": "Yield OT 10A",
        "kpi_npl": "Rácio de NPL",
        "kpi_vs_prev": "vs ant.",
        # Generic section labels
        "key_findings": "Principais Conclusões",
        "descriptive_statistics": "Estatísticas Descritivas ({start}&ndash;{end})",
        "risk_assessment": "Avaliação de Risco:",
        "outlook": "Perspetivas",
        "source": "Fonte",
        "interactive_note": "interativo: zoom, hover, download",
        # Stats table headers
        "th_indicator": "Indicador",
        "th_mean": "Média",
        "th_std": "Desvio-Padrão",
        "th_median": "Mediana",
        # TOC labels (non-pillar)
        "toc_key_indicators": "Indicadores-Chave",
        "toc_executive_dashboard": "Painel Executivo",
        "toc_cross_pillar": "Análise Inter-Pilares",
        "toc_stl": "Decomposição STL",
        "toc_forecasting": "Previsão SARIMAX",
        "toc_benchmarking": "Benchmarking UE",
        "toc_regional": "Análise Regional (NUTS2)",
        "toc_risk_matrix": "Matriz de Risco",
        "toc_recommendations": "Recomendações Estratégicas",
        "toc_platform": "Plataforma &amp; Ferramentas",
        "toc_methodology": "Metodologia",
        # Cross-pillar
        "cross_pillar_title": "Análise Inter-Pilares",
        "cap_correlation": "Matriz de correlação inter-pilares",
        "cap_phillips": "Curva de Phillips: desemprego vs inflação",
        "cap_crisis": "Cronologia de crises: períodos de stress macroeconómico",
        # Benchmarking
        "benchmarking_title": "Benchmarking UE",
        "benchmarking_intro": "Desempenho macroeconómico de Portugal comparado com os "
        "principais pares europeus (Alemanha, Espanha, França, Itália) e as médias da "
        "UE / Zona Euro.",
        "cap_radar": "Portugal vs médias da UE — radar normalizado",
        "cap_small_multiples": "Comparação com países pares — indicadores-chave",
        # Regional
        "regional_title": "Análise Regional — NUTS2",
        "regional_intro": "O desempenho macroeconómico de Portugal varia "
        "significativamente entre as suas sete regiões NUTS2. Lisboa concentra uma "
        "parcela desproporcional do PIB nacional, enquanto as regiões periféricas "
        "enfrentam desafios estruturais de competitividade e emprego.",
        "regional_th_code": "Código",
        "regional_th_region": "Região",
        "regional_th_gdp": "PIB per Capita (PPC)",
        "regional_th_unemp": "Desemprego",
        "regional_map_title": "PIB per capita por região NUTS2 (PPC), último ano",
        "regional_map_note": "mapa coroplético interativo — passe o rato sobre cada região",
        "regional_source": "Eurostat (nama_10r_2gdp)",
        "regional_synthetic_note": "Nota: dados baseados em estimativas sintéticas — "
        "execute <code>python main.py</code> para carregar dados reais.",
        # Executive dashboard
        "exec_dashboard_title": "Painel Executivo",
        "exec_dashboard_intro": "Resumo numa única vista dos seis pilares "
        "macroeconómicos — PIB, desemprego, crédito, taxas de juro, inflação e dívida "
        "pública — de {start} a {end}.",
        "exec_dashboard_caption": "Os seis pilares centrais num relance, {start}&ndash;{end}",
        # STL
        "stl_title": "Decomposição Sazonal-Tendência (STL)",
        "stl_intro": "Decomposição das principais séries temporais económicas em "
        "componentes de tendência, sazonal e residual usando STL (Seasonal and Trend "
        "decomposition using Loess). Revela as tendências estruturais subjacentes, "
        "isentas do ruído sazonal.",
        "cap_stl_gdp": "Decomposição STL: PIB real",
        "cap_stl_unemployment": "Decomposição STL: taxa de desemprego",
        "cap_stl_inflation": "Decomposição STL: inflação IHPC",
        # Forecasting
        "forecasting_title": "Previsão SARIMAX",
        "forecasting_intro": "Previsões a 12 trimestres geradas por modelos SARIMAX "
        "com seleção automática de ordem via AIC. Os modelos são guardados em cache "
        "durante 7 dias (joblib) e reestimados quando chegam novos dados. As bandas "
        "sombreadas mostram intervalos de previsão de 68% e 95%; os diagnósticos de "
        "resíduos incluem o teste de Ljung-Box.",
        "fc_th_indicator": "Indicador",
        "fc_th_latest_period": "Último Período",
        "fc_th_latest_value": "Último Valor",
        "fc_th_horizon": "Horizonte",
        "fc_th_forecast": "Previsão",
        "fc_th_direction": "Direção",
        "fc_historical": "Histórico",
        "fc_forecast_name": "Previsão {method}",
        "fc_chart_title": "{indicator} — previsão a 12 trimestres",
        "fc_source": "Conjunto de modelos Portugal Data Intelligence",
        "fc_note": "método: {method}; as bandas sombreadas são intervalos de 68% / 95%",
        # Risk matrix
        "risk_matrix_title": "Matriz de Risco",
        "rm_th_pillar": "Pilar",
        "rm_th_level": "Nível de Risco",
        "rm_th_assessment": "Avaliação",
        # Recommendations
        "recommendations_title": "Recomendações Estratégicas",
        # Platform
        "platform_title": "Plataforma &amp; Ferramentas",
        "platform_intro": "O Portugal Data Intelligence v{version} entrega insights "
        "através de múltiplos canais complementares, cada um adaptado a um público e "
        "caso de uso diferentes.",
        "platform_dashboard_h": "Dashboard Interativo (Streamlit)",
        "platform_dashboard_p": "Dashboard web de quatro páginas com cartões de KPI em "
        "tempo real, análise aprofundada por pilar com intervalo de anos e filtros de "
        "indicadores configuráveis, heatmap de correlação inter-pilares com análise da "
        "curva de Phillips, e um explorador de dados em bruto com download em CSV.",
        "platform_api_h": "API REST (FastAPI)",
        "platform_api_p": "Sete endpoints que expõem os dados macroeconómicos de forma "
        "programática: listagem de pilares, últimos valores com estatísticas-resumo, "
        "consultas filtradas de séries temporais, monitorização de alertas ativos e "
        "matrizes de correlação inter-pilares. Documentação OpenAPI completa em "
        "<code>/docs</code>.",
        "platform_forecast_h": "Previsão por Ensemble",
        "platform_forecast_p": "Previsão multi-modelo que combina SARIMAX, "
        "Holt-Winters, tendência linear, reversão à média e modelos log-lineares. Os "
        "modelos são ponderados automaticamente pelo inverso do MAE de backtesting de "
        "janela expansível, produzindo projeções de consenso robustas com bandas de "
        "confiança de 68% e 95%.",
        "platform_powerbi_h": "Dashboard Power BI",
        "platform_powerbi_p": "39 medidas DAX em 7 categorias (KPIs, crescimento "
        "homólogo, médias móveis, métricas derivadas, comparações de períodos, "
        "formatação, colunas calculadas) para dashboards interativos de nível "
        "empresarial com drill-down e análise what-if.",
        "platform_footnote": "Adicionalmente, a plataforma inclui um "
        "<strong>motor de alertas</strong> configurável com limiares de "
        "aviso/crítico para 11 indicadores ao longo dos pilares económicos, uma "
        "<strong>cache de respostas da API</strong> para reduzir chamadas HTTP "
        "redundantes ao Eurostat, BCE e Banco de Portugal, e um "
        "<strong>pipeline de CI/CD</strong> abrangente (GitHub Actions) com linting, "
        "testes em Python 3.10&ndash;3.12 e relatórios de cobertura automatizados.",
        "launch": "Arrancar:",
        # Methodology
        "methodology_title": "Metodologia &amp; Fontes de Dados",
        "methodology_intro": "Este relatório analisa a economia portuguesa ao longo de "
        "doze pilares macroeconómicos, mais a análise regional NUTS2, usando dados de "
        "{start} a {end}. Os pilares macrofinanceiros centrais (PIB, desemprego, "
        "inflação, taxas de juro, crédito, dívida pública) e as séries de desigualdade "
        "e regionais reproduzem os valores oficiais publicados pelas instituições "
        "abaixo. Os pilares da habitação, estrutura do trabalho, contas externas e "
        "orçamental são séries modeladas calibradas às publicações oficiais "
        "correspondentes (Eurostat, INE, Banco de Portugal); seguem os níveis e a "
        "dinâmica publicados, mas não são os registos oficiais em bruto.",
        "methodology_th_source": "Fonte",
        "methodology_th_url": "URL",
        "methodology_granularity": "<strong>Granularidade:</strong> PIB, Dívida Pública "
        "e Contas Externas são trimestrais; Desemprego, Crédito, Taxas de Juro e "
        "Inflação são mensais; Habitação, Detalhe do Trabalho, Orçamental, Desigualdade "
        "e Regional são anuais.",
        "methodology_quality": "<strong>Qualidade dos Dados:</strong> Todos os pilares "
        "passam um quadro de validação de 8 verificações (esquema, nulos, intervalos, "
        "outliers, deriva, completude, consistência, atualidade).",
        "methodology_engine": "<strong>Motor de Análise:</strong> Python (pandas, "
        "statsmodels, scipy) com armazenamento em SQLite, previsão por ensemble e "
        "geração automatizada de relatórios.",
        "methodology_delivery": "<strong>Entrega:</strong> Power BI, dashboard "
        "Streamlit, HTML auto-contido, API REST (FastAPI).",
        "methodology_version": "<strong>Versão:</strong> {version} &mdash; Gerado em " "{date}",
        # Footer
        "footer_author_line": "Portugal Data Intelligence v{version}",
        "footer_tagline": "Diogo Serino &middot; Portefólio 2026 &middot; Power BI "
        "&middot; Streamlit &middot; FastAPI &middot; HTML",
        "footer_generated": "Relatório gerado: {generated}",
        # Language switch
        "lang_switch_label": "Idioma",
    },
}


def tr(lang: str) -> Dict[str, str]:
    """Return the STRINGS table for ``lang`` (falls back to the default)."""
    return STRINGS.get(lang, STRINGS[DEFAULT_LANG])
