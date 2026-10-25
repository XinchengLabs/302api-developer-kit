"""Offline public-price arithmetic. No accounts, payments, holds, or network I/O.

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow, ROUND_FLOOR, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
import re
import sys
from typing import Any


MILLION = Decimal(1_000_000)
SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
CATEGORIES = ("input_uncached", "cache_read", "cache_write", "cache_write_5m", "cache_write_1h", "output")
PRICE_FIELDS = {
    "input_uncached": "customer_input_price",
    "cache_read": "customer_cached_input_price",
    "cache_write": "customer_cache_write_price",
    "cache_write_5m": "customer_cache_write_price",
    "cache_write_1h": "customer_cache_write_1h_price",
    "output": "customer_output_price",
}


def _decimal_context(precision: int) -> Context:
    # Do not inherit precision, exponent limits, rounding or traps from callers.
    return Context(prec=precision, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow])


class CalculationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def fail(code: str, message: str) -> None:
    raise CalculationError(code, message)


def load_json(text: str) -> Any:
    """Parse decimal numbers losslessly, rejecting duplicate keys and NaN."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail("duplicate_json_key", "JSON contains a duplicate key.")
            result[key] = value
        return result

    def constant(_):
        fail("nonfinite_number", "NaN and Infinity are not valid billing data.")

    try:
        return json.loads(text, parse_float=Decimal, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as error:
        fail("invalid_json", f"Invalid JSON at line {error.lineno}, column {error.colno}.")


def _object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        fail("invalid_object", f"{field} must be a JSON object.")
    return value


def _count(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        fail("invalid_token_count", f"{field} must be a nonnegative JSON integer.")
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (str, int, Decimal)):
        fail("invalid_price", f"{field} needs an exact decimal string, Decimal or integer; use load_json().")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        fail("invalid_price", f"{field} is not a decimal number.")
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        fail("invalid_price", f"{field} must be finite and {'positive' if positive else 'nonnegative'}.")
    if result and (result.adjusted() < -30 or result.adjusted() > 18 or len(result.as_tuple().digits) > 50):
        fail("unsupported_numeric_precision", f"{field} exceeds the calculator's decimal range.")
    return result if result else Decimal(0)


def _zero_only(value: Any) -> bool:
    if type(value) is int:
        return value == 0
    if isinstance(value, Decimal):
        return value.is_finite() and value == 0
    if isinstance(value, dict):
        return all(_zero_only(v) for v in value.values())
    return False


def _unknown_fields(data: dict, known: set[str], field: str) -> None:
    for key, value in data.items():
        if key not in known and not _zero_only(value):
            fail("unsupported_usage_category", f"Unsupported nonzero or unknown category in {field}: {key}.")


def _aliases(values: list[tuple[dict, str]], field: str, default: int = 0) -> int:
    found = [_count(obj[key], field) for obj, key in values if key in obj]
    if found and any(value != found[0] for value in found):
        fail("conflicting_usage", f"Conflicting aliases for {field}.")
    return found[0] if found else default


def _cache_write(usage: dict, details: dict, ttl: str | None) -> tuple[int, int, int]:
    totals = [(obj, key) for obj, key in ((usage, "cache_creation_input_tokens"), (details, "cache_write_tokens")) if key in obj]
    total = _aliases(totals, "cache write total")
    breakdowns = []
    for obj in (usage, details):
        if "cache_creation" not in obj:
            continue
        item = _object(obj["cache_creation"], "cache_creation")
        _unknown_fields(item, {"ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"}, "cache_creation")
        if not item:
            continue
        short = _count(item.get("ephemeral_5m_input_tokens", 0), "5m cache writes")
        long = _count(item.get("ephemeral_1h_input_tokens", 0), "1h cache writes")
        breakdowns.append((short, long))
    if breakdowns:
        if any(item != breakdowns[0] for item in breakdowns):
            fail("conflicting_usage", "Conflicting cache creation breakdowns.")
        short, long = breakdowns[0]
        if totals and short + long != total:
            fail("cache_write_mismatch", "5m plus 1h writes must equal total cache writes.")
        return 0, short, long
    if total and ttl:
        return (0, total, 0) if ttl == "5m" else (0, 0, total)
    return total, 0, 0


def normalize_usage(usage: dict, usage_format: str, cache_write_ttl: str | None = None) -> dict[str, int]:
    """Return mutually exclusive categories; never estimate missing required use."""
    usage = _object(usage, "usage")
    if cache_write_ttl not in (None, "5m", "1h"):
        fail("invalid_cache_ttl", "cache_write_ttl must be 5m or 1h.")
    if usage_format == "normalized":
        _unknown_fields(usage, set(CATEGORIES) | {"input_total"}, "normalized usage")
        if any(key not in usage for key in CATEGORIES):
            fail("missing_usage", "Normalized usage must explicitly provide all six categories, including zeros.")
        result = {key: _count(usage[key], key) for key in CATEGORIES}
        if result["cache_write"] and (result["cache_write_5m"] or result["cache_write_1h"]):
            fail("cache_write_mismatch", "Generic and TTL-split writes cannot both be positive.")
        if result["cache_write"] and cache_write_ttl:
            result["cache_write_" + cache_write_ttl] = result["cache_write"]
            result["cache_write"] = 0
        result["input_total"] = sum(result[key] for key in CATEGORIES if key != "output")
        if "input_total" in usage and _count(usage["input_total"], "input_total") != result["input_total"]:
            fail("conflicting_usage", "Normalized input_total does not match its exclusive categories.")
        return result

    if usage_format not in ("openai-chat", "openai-responses", "anthropic"):
        fail("unsupported_usage_format", "Choose openai-chat, openai-responses, anthropic or normalized.")
    is_chat = usage_format == "openai-chat"
    is_native = usage_format == "anthropic"
    input_key = "prompt_tokens" if is_chat else "input_tokens"
    output_key = "completion_tokens" if is_chat else "output_tokens"
    details_key = "prompt_tokens_details" if is_chat else "input_tokens_details"
    output_details_key = "completion_tokens_details" if is_chat else "output_tokens_details"
    known = {input_key, output_key, "total_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "cache_creation", "service_tier"}
    if not is_native:
        known |= {details_key, output_details_key, "cached_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"}
    _unknown_fields(usage, known, "usage")
    if "service_tier" in usage and usage["service_tier"] not in ("standard", "default"):
        fail("unsupported_service_tier", "Only standard/default price tiers are supported.")
    if input_key not in usage or output_key not in usage:
        fail("missing_usage", f"{input_key} and {output_key} are required.")
    input_count = _count(usage[input_key], input_key)
    output_count = _count(usage[output_key], output_key)
    details = _object(usage[details_key], details_key) if details_key in usage else {}
    output_details = _object(usage[output_details_key], output_details_key) if output_details_key in usage else {}
    _unknown_fields(details, {"cached_tokens", "cache_write_tokens", "cache_creation", "text_tokens"}, details_key)
    _unknown_fields(output_details, {"reasoning_tokens", "text_tokens"}, output_details_key)
    for obj, field in ((details, "text_tokens"), (output_details, "text_tokens"), (output_details, "reasoning_tokens")):
        if field in obj:
            value = _count(obj[field], field)
            if value > (input_count if obj is details else output_count):
                fail("conflicting_usage", f"{field} exceeds its parent token count.")
    read = _aliases([(usage, "cache_read_input_tokens"), (details, "cached_tokens"), (usage, "cached_tokens"), (usage, "prompt_cache_hit_tokens")], "cache read")
    generic, short, long = _cache_write(usage, details, cache_write_ttl)
    written = generic + short + long
    if is_native:
        ordinary, input_total = input_count, input_count + read + written
    else:
        if read + written > input_count:
            fail("cache_exceeds_input", "Cached categories exceed total input.")
        ordinary, input_total = input_count - read - written, input_count
        if "prompt_cache_miss_tokens" in usage and _count(usage["prompt_cache_miss_tokens"], "prompt_cache_miss_tokens") != input_total - read:
            fail("conflicting_usage", "Cache hit/miss counts disagree with total input.")
    if "total_tokens" in usage and _count(usage["total_tokens"], "total_tokens") != input_total + output_count:
        fail("conflicting_usage", "total_tokens does not equal input plus output.")
    return {"input_uncached": ordinary, "cache_read": read, "cache_write": generic,
            "cache_write_5m": short, "cache_write_1h": long, "output": output_count,
            "input_total": input_total}


def _timestamp(value: Any) -> tuple[datetime, Decimal]:
    with localcontext(_decimal_context(100)):
        return _timestamp_value(value)


def _timestamp_value(value: Any) -> tuple[datetime, Decimal]:
    if isinstance(value, bool) or isinstance(value, float):
        fail("invalid_timestamp", "Use an aware ISO timestamp or an exact Unix timestamp.")
    if isinstance(value, str) and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        if re.search(r"[.,]\d{7,}", value):
            fail("unsupported_timestamp_precision", "Timestamps support at most microsecond precision.")
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                fail("timezone_required", "Timestamp must include a timezone offset.")
            instant = instant.astimezone(timezone.utc)
            delta = instant - EPOCH
            return instant, Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / MILLION
        except CalculationError:
            raise
        except (ValueError, OverflowError):
            fail("invalid_timestamp", "Invalid timestamp; include date, time and timezone.")
    if not isinstance(value, (str, int, Decimal)):
        fail("invalid_timestamp", "Missing or unsupported timestamp.")
    try:
        epoch = Decimal(value)
        if not epoch.is_finite():
            raise ValueError
        parts = epoch.as_tuple()
        if len(parts.digits) > 32 or not -30 <= parts.exponent <= 18:
            fail("unsupported_timestamp_precision", "Unix seconds support at most 32 digits and 30 decimal places.")
        # Preserve full epoch precision for quote windows; floor only datetime's
        # microsecond display/schedule conversion (also correct before 1970).
        micros = (epoch * MILLION).to_integral_value(rounding=ROUND_FLOOR)
        instant = EPOCH + timedelta(microseconds=int(micros))
        return instant, epoch
    except CalculationError:
        raise
    except (ValueError, InvalidOperation, OverflowError):
        fail("invalid_timestamp", "Unix timestamp is not finite or outside the supported date range.")


def _window(begin: Any, end: Any, epoch: Decimal) -> bool:
    _, low = _timestamp(begin)
    _, high = _timestamp(end)
    if high <= low:
        fail("invalid_quote_window", "Quote validity must end after it starts.")
    return low <= epoch < high


def _clock(value: Any) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        fail("invalid_calendar", "Peak windows need HH:MM times.")
    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes


def _period(instant: datetime, rule: dict, calendar: dict) -> tuple[str, str]:
    calendar = _object(calendar, "calendar")
    if calendar.get("timezone") != "Asia/Shanghai" or calendar.get("utc_offset_minutes") != 480:
        fail("unsupported_calendar", "This rule requires explicit Asia/Shanghai UTC+08:00 data.")
    if calendar.get("version") != rule.get("calendar_version") or calendar.get("rule_version") != rule.get("rule_version"):
        fail("calendar_version_mismatch", "Calendar and price-rule versions must match.")
    if calendar.get("weekends_off_peak") is not True:
        fail("unsupported_calendar", "Only the published weekends-off-peak rule is supported.")
    local = instant.astimezone(SHANGHAI)
    years = _object(calendar.get("holidays_by_year"), "holidays_by_year")
    holidays = years.get(str(local.year))
    if not isinstance(holidays, list):
        fail("calendar_year_missing", "No confirmed calendar for this request year.")
    for day in holidays:
        try:
            parsed = date.fromisoformat(day)
        except (ValueError, TypeError):
            fail("invalid_calendar", "Invalid holiday date.")
        if parsed.year != local.year:
            fail("invalid_calendar", "Holiday dates must belong to their declared year.")
    windows = calendar.get("peak_windows")
    if not isinstance(windows, list) or not windows:
        fail("invalid_calendar", "Peak windows are required.")
    ranges = []
    for window in windows:
        if not isinstance(window, list) or len(window) != 2:
            fail("invalid_calendar", "Each peak window needs a start and end.")
        start, end = map(_clock, window)
        if end <= start:
            fail("invalid_calendar", "Peak windows cannot wrap across midnight.")
        ranges.append((start, end))
    if local.weekday() >= 5:
        return "off_peak", "weekend"
    if local.date().isoformat() in holidays:
        return "off_peak", "holiday"
    minute = local.hour * 60 + local.minute
    if any(start <= minute < end for start, end in ranges):
        return "peak", "peak_window"
    return "off_peak", "off_peak_hours"


def _prices(model: dict, catalog: dict, instant: datetime, epoch: Decimal,
            calendar: dict | None, strict: bool) -> tuple[dict, dict | None, list[str]]:
    warnings = ["Formula-only result: supplied prices are not proof of the historical request's locked prices."]
    rule = model.get("time_pricing")
    if rule is None:
        if strict:
            meta = _object(catalog.get("_metadata", {}), "_metadata")
            window = _object(meta.get("quote_window"), "quote_window")
            if not _window(window.get("valid_from"), window.get("valid_until"), epoch):
                fail("quote_out_of_window", "Request start is outside the supplied quote window.")
        return model, None, warnings
    rule = _object(rule, "time_pricing")
    if rule.get("price_basis") != "request_start":
        fail("unsupported_price_basis", "Time prices must use request_start.")
    in_window = False
    if "quoted_at" in rule and "valid_until" in rule:
        in_window = _window(rule["quoted_at"], rule["valid_until"], epoch)
    if strict and not in_window:
        fail("quote_out_of_window", "Request start is outside the supplied time-price quote window.")
    if calendar is not None:
        period, reason = _period(instant, rule, calendar)
        if in_window and rule.get("period") != period:
            fail("conflicting_time_price", "Calendar period conflicts with the quoted period.")
    elif in_window and rule.get("calendar_confirmed") is True and rule.get("period") in ("peak", "off_peak"):
        period, reason = rule["period"], "provided_quote"
    else:
        fail("calendar_required", "An out-of-window time quote requires an explicit versioned calendar.")
    tiers = _object(rule.get("tiers"), "time_pricing.tiers")
    selected = _object(tiers.get(period), "selected time tier")
    prices = dict(model)
    for field in ("customer_input_price", "customer_cached_input_price", "customer_output_price"):
        if field not in selected:
            fail("missing_price", "Selected time tier lacks an explicit customer price.")
    for field in set(PRICE_FIELDS.values()):
        # Never mix an earlier/current top-level price into the selected tier.
        prices[field] = selected.get(field)
    if not in_window:
        warnings.append("Time tier was selected by the supplied calendar; historical price validity remains unverified.")
    return prices, {"period": period, "reason": reason, "rule_version": rule.get("rule_version"),
                    "calendar_version": rule.get("calendar_version"), "price_basis": "request_start",
                    "within_supplied_quote_window": in_window,
                    "request_started_at_local": instant.astimezone(SHANGHAI).isoformat()}, warnings


def calculate(request: dict, catalog: dict, calendar: dict | None = None) -> dict:
    """Pure arithmetic over caller-provided public facts; inputs are never mutated."""
    request = _object(request, "request")
    catalog = _object(catalog, "catalog")
    metadata = _object(catalog.get("_metadata", {}), "_metadata")
    if metadata.get("schema_version", 1) != 1:
        fail("unsupported_catalog_version", "Only catalog schema version 1 is supported.")
    if metadata.get("currency", "USD") != "USD" or metadata.get("price_unit", "USD_per_million_tokens") != "USD_per_million_tokens":
        fail("unsupported_price_unit", "Prices must be USD per million tokens.")
    allowed = {"model_id", "request_started_at", "usage_format", "usage", "input_modality",
               "cache_write_ttl", "exchange_rate", "require_valid_quote"}
    if set(request) - allowed:
        fail("unsupported_request_field", "Request contains fields outside the calculator schema.")
    if request.get("input_modality") != "text":
        fail("unsupported_modality", "Declare input_modality=text; image/audio/tool fees are not supported.")
    strict = request.get("require_valid_quote", False)
    if type(strict) is not bool:
        fail("invalid_quote_requirement", "require_valid_quote must be a boolean.")
    model_id = request.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        fail("model_required", "model_id is required; IDs match exactly.")
    items = catalog.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        fail("invalid_catalog", "Price catalog must contain an items array.")
    ids = [item.get("model_id") for item in items]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        fail("invalid_catalog", "Catalog model IDs must be nonempty and unique.")
    matches = [item for item in items if item["model_id"] == model_id]
    if not matches:
        fail("model_not_found", "No exact model ID in the supplied price catalog.")
    model = matches[0]
    if model.get("model_type") != "chat" or model.get("modality_prices") is not None:
        fail("unsupported_modality", "Initial calculator supports text/chat pricing without separate modality rates.")
    instant, epoch = _timestamp(request.get("request_started_at"))
    tokens = normalize_usage(request.get("usage"), request.get("usage_format"), request.get("cache_write_ttl"))
    if tokens["cache_write"] and model.get("cache_write_duration_pricing"):
        fail("cache_ttl_required", "Cache writes need explicit 5m/1h evidence or a request TTL.")
    prices, time_info, warnings = _prices(model, catalog, instant, epoch, calendar, strict)
    context = model.get("context_pricing")
    multipliers = {"input": Decimal(1), "cache": Decimal(1), "output": Decimal(1)}
    threshold, long_context = None, False
    if context is not None:
        context = _object(context, "context_pricing")
        if context.get("scope") != "whole_request":
            fail("unsupported_context_rule", "Only whole_request context tiers are supported.")
        threshold = _count(context.get("standard_max_input_tokens"), "context threshold")
        long_context = tokens["input_total"] > threshold
        factors = {kind: _number(context.get("long_" + kind + "_multiplier"), "context multiplier", positive=True)
                   for kind in multipliers}
        if long_context:
            multipliers = factors
    precision = max(300, max(len(str(value)) for value in tokens.values()) + 250)
    with localcontext(_decimal_context(precision)):
        units, charges = Decimal(0), []
        for category in CATEGORIES:
            count = tokens[category]
            if not count:
                continue
            field = PRICE_FIELDS[category]
            if prices.get(field) is None:
                fail("missing_price", f"Explicit customer price required for {category}.")
            price = _number(prices[field], field)
            kind = "output" if category == "output" else "input" if category == "input_uncached" else "cache"
            multiplier = multipliers[kind]
            amount_units = Decimal(count) * price * multiplier
            units += amount_units
            charges.append({"category": category, "tokens": count,
                            "unit_price_usd_per_million": format(price, "f"),
                            "multiplier": format(multiplier, "f"),
                            "amount_usd_unrounded": format(amount_units / MILLION, "f")})
        micros = int(units.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        cny = None
        if "exchange_rate" in request:
            exchange_rate = _number(request["exchange_rate"], "exchange_rate", positive=True)
            cny_micros = int((units * exchange_rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            cny = {"amount": format(Decimal(cny_micros) / MILLION, ".6f"),
                   "amount_micros": cny_micros, "exchange_rate": format(exchange_rate, "f"),
                   "scope": "single-request formula only; not a balance delta"}
        else:
            warnings.append("No request exchange rate supplied; no CNY amount calculated.")
        return {"schema_version": 1, "model_id": model_id,
                "request_started_at": instant.isoformat(), "request_started_at_epoch": format(epoch, "f"),
                "calculation_scope": "public_formula_only", "historical_price_match_verified": False,
                "tokens": tokens, "charges": charges,
                "context_pricing": {"applied": long_context, "threshold_input_tokens": threshold,
                                    "scope": "whole_request", "input_multiplier": format(multipliers["input"], "f"),
                                    "cache_multiplier": format(multipliers["cache"], "f"),
                                    "output_multiplier": format(multipliers["output"], "f")},
                "time_pricing": time_info, "amount_usd_unrounded": format(units / MILLION, "f"),
                "amount_usd": format(Decimal(micros) / MILLION, ".6f"), "amount_usd_micros": micros,
                "cny": cny, "rounding": {"decimals": 6, "mode": "ROUND_HALF_UP", "stage": "total_only",
                                          "cny_basis": "unrounded USD, independently rounded"},
                "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline text/cache cost verification from explicit public prices.")
    parser.add_argument("--prices", required=True, type=Path, help="Public catalog JSON with items")
    parser.add_argument("--request", required=True, help="Request JSON path, or - for stdin")
    parser.add_argument("--calendar", type=Path, default=Path(__file__).with_name("calendar-2026.json"))
    args = parser.parse_args()
    try:
        catalog = load_json(args.prices.read_text(encoding="utf-8"))
        request = load_json(sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8"))
        calendar = load_json(args.calendar.read_text(encoding="utf-8")) if args.calendar.exists() else None
        print(json.dumps(calculate(request, catalog, calendar), ensure_ascii=False, indent=2))
        return 0
    except (CalculationError, OSError) as error:
        code = error.code if isinstance(error, CalculationError) else "file_error"
        print(json.dumps({"error": {"code": code, "message": str(error)}}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
