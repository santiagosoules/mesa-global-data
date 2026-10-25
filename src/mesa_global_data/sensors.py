from __future__ import annotations

from typing import Dict

from .models import SensorDefinition


SENSORS: Dict[str, SensorDefinition] = {
    "us2y_yield": SensorDefinition(
        "us2y_yield", "rates", "U.S. Treasury 2Y yield", "percent",
        "U.S. Treasury 2-Year Constant Maturity", "daily", 5, "U.S. Treasury",
    ),
    "us10y_yield": SensorDefinition(
        "us10y_yield", "rates", "U.S. Treasury 10Y yield", "percent",
        "U.S. Treasury 10-Year Constant Maturity", "daily", 5, "U.S. Treasury",
    ),
    "us10y_real_yield": SensorDefinition(
        "us10y_real_yield", "rates", "U.S. Treasury 10Y real yield", "percent",
        "U.S. Treasury 10-Year TIPS Constant Maturity", "daily", 5, "U.S. Treasury",
    ),
    "fed_balance_assets": SensorDefinition(
        "fed_balance_assets", "fed", "Federal Reserve total assets", "million_usd",
        "Federal Reserve H.4.1 total assets, Wednesday level", "weekly", 12, "Federal Reserve Board H.4.1",
    ),
    "tga_balance": SensorDefinition(
        "tga_balance", "liquidity", "Treasury General Account", "million_usd",
        "U.S. Treasury General Account, Wednesday level", "weekly", 12, "Federal Reserve Board H.4.1",
    ),
    "on_rrp_usage": SensorDefinition(
        "on_rrp_usage", "liquidity", "Overnight reverse repo usage", "billion_usd",
        "NY Fed ON RRP accepted amount", "daily", 5, "Federal Reserve Bank of New York",
    ),
    "bank_reserves": SensorDefinition(
        "bank_reserves", "liquidity", "Reserve balances", "million_usd",
        "Reserve balances with Federal Reserve Banks, Wednesday level", "weekly", 12, "Federal Reserve Board H.4.1",
    ),
    "ofr_fsi_credit": SensorDefinition(
        "ofr_fsi_credit", "credit", "OFR FSI credit contribution", "standard_deviation_contribution",
        "OFR Financial Stress Index credit-market contribution", "daily", 5, "Office of Financial Research",
    ),
    "ofr_fsi_us": SensorDefinition(
        "ofr_fsi_us", "credit", "OFR FSI United States contribution", "standard_deviation_contribution",
        "OFR Financial Stress Index United States contribution", "daily", 5, "Office of Financial Research",
    ),
    "nq_cot_leveraged_funds_net": SensorDefinition(
        "nq_cot_leveraged_funds_net", "cot", "NQ/MNQ consolidated leveraged funds net",
        "nq_equivalent_contracts", "CFTC NASDAQ-100 Consolidated Futures Only", "weekly", 10, "CFTC TFF Futures Only",
    ),
    "nq_cot_asset_manager_net": SensorDefinition(
        "nq_cot_asset_manager_net", "cot", "NQ/MNQ consolidated asset manager net",
        "nq_equivalent_contracts", "CFTC NASDAQ-100 Consolidated Futures Only", "weekly", 10, "CFTC TFF Futures Only",
    ),
    "nq_cot_open_interest": SensorDefinition(
        "nq_cot_open_interest", "cot", "NQ/MNQ consolidated open interest",
        "nq_equivalent_contracts", "CFTC NASDAQ-100 Consolidated Futures Only", "weekly", 10, "CFTC TFF Futures Only",
    ),
}

