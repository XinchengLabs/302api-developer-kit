# SPDX-License-Identifier: LicenseRef-302API-Community-Commercial-1.0
"""Synthetic formula tests only: no network, customer data, or account state."""
import copy
import ast
import builtins
from contextlib import ExitStack, contextmanager
from datetime import datetime
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, ROUND_FLOOR, localcontext
import importlib
import io
import os
from pathlib import Path
import socket
import unittest
from unittest import mock

from calculator import CalculationError, calculate, load_json, normalize_usage


START = "2026-10-25T06:00:00+08:00"
START_EPOCH = int(datetime.fromisoformat(START).timestamp())
ALLOWED_IMPORTS = {"__future__", "argparse", "datetime", "decimal", "json", "pathlib", "re", "sys", "typing"}


@contextmanager
def no_runtime_io():
    """Guard module-body execution / pure calls, not Python's source loader."""
    for name in ALLOWED_IMPORTS:
        importlib.import_module(name)
    original_import = builtins.__import__

    def deny(*args, **kwargs):
        raise AssertionError("Formula execution attempted file, environment or network I/O")

    def allowed_import(name, *args, **kwargs):
        if name not in ALLOWED_IMPORTS:
            raise AssertionError("Formula execution imported an unreviewed module: " + name)
        return original_import(name, *args, **kwargs)

    with ExitStack() as stack:
        for owner, name in (
            (builtins, "open"), (io, "open"), (os, "open"),
            (Path, "open"), (Path, "read_text"), (Path, "read_bytes"),
            (os, "getenv"), (os._Environ, "__getitem__"),
            (os._Environ, "__iter__"), (socket, "socket"),
            (socket, "create_connection"),
        ):
            stack.enter_context(mock.patch.object(owner, name, deny))
        stack.enter_context(mock.patch.object(builtins, "__import__", allowed_import))
        yield


def synthetic_model(**changes):
    model = {
        "model_id": "synthetic-chat",
        "display_name": "Synthetic test model",
        "model_type": "chat",
        "price_provider": "synthetic",
        "customer_input_price": "2",
        "customer_output_price": "10",
        "customer_cached_input_price": "0.2",
        "customer_cache_write_price": "2.5",
        "customer_cache_write_1h_price": "4",
        "cache_write_duration_pricing": True,
        "context_pricing": None,
        "time_pricing": None,
        "modality_prices": None,
    }
    model.update(changes)
    return model


def counts(**changes):
    values = {
        "input_uncached": 1000,
        "cache_read": 0,
        "cache_write": 0,
        "cache_write_5m": 0,
        "cache_write_1h": 0,
        "output": 500,
    }
    values.update(changes)
    return values


def request(usage=None, usage_format="normalized", **changes):
    value = {
        "model_id": "synthetic-chat",
        "request_started_at": START,
        "usage_format": usage_format,
        "usage": counts() if usage is None else usage,
        "input_modality": "text",
    }
    value.update(changes)
    return value


def context_model(threshold=100, input_factor="5", cache_factor="5", output_factor="5"):
    return synthetic_model(context_pricing={
        "standard_max_input_tokens": threshold,
        "long_input_multiplier": input_factor,
        "long_cache_multiplier": cache_factor,
        "long_output_multiplier": output_factor,
        "scope": "whole_request",
    })


def time_model():
    return synthetic_model(
        price_provider="deepseek",
        customer_input_price="1",
        customer_output_price="5",
        customer_cached_input_price="0.1",
        global_discount_rate="0.26",
        time_pricing={
            "period": "off_peak",
            "factor": "0.5",
            "quoted_at": START_EPOCH,
            "valid_until": START_EPOCH + 60,
            "timezone": "Asia/Shanghai",
            "calendar_confirmed": True,
            "calendar_version": "synthetic-calendar",
            "rule_version": "synthetic-rule",
            "price_basis": "request_start",
            "discount_rate": "0.26",
            "tiers": {
                "peak": {
                    "customer_input_price": "2",
                    "customer_cached_input_price": "0.2",
                    "customer_output_price": "10",
                },
                "off_peak": {
                    "customer_input_price": "1",
                    "customer_cached_input_price": "0.1",
                    "customer_output_price": "5",
                },
            },
        },
    )


def synthetic_calendar():
    """A synthetic schedule fixture, not a production calendar export."""
    return {
        "version": "synthetic-calendar",
        "rule_version": "synthetic-rule",
        "timezone": "Asia/Shanghai",
        "utc_offset_minutes": 480,
        "weekends_off_peak": True,
        "peak_windows": [["09:00", "12:00"], ["14:00", "18:00"]],
        "holidays_by_year": {"2026": ["2026-10-01"]},
    }


class FormulaTests(unittest.TestCase):
    def quote(self, value=None, model=None, catalog_changes=None):
        catalog = {"items": [model or synthetic_model()]}
        catalog.update(catalog_changes or {})
        return calculate(value or request(), catalog)

    def test_openai_cached_tokens_are_subtracted_from_total_input(self):
        raw = {"prompt_tokens": 1000, "completion_tokens": 500,
               "total_tokens": 1500, "prompt_tokens_details": {"cached_tokens": 400}}
        normalized = normalize_usage(raw, "openai-chat")
        self.assertEqual(normalized["input_uncached"], 600)
        self.assertEqual(normalized["cache_read"], 400)
        self.assertEqual(normalized["input_total"], 1000)
        self.assertEqual(self.quote(request(raw, "openai-chat"))["amount_usd"], "0.006280")

    def test_responses_reasoning_is_not_added_to_output_twice(self):
        raw = {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500,
               "input_tokens_details": {"cached_tokens": 400},
               "output_tokens_details": {"reasoning_tokens": 100}}
        normalized = normalize_usage(raw, "openai-responses")
        self.assertEqual(normalized["output"], 500)
        self.assertEqual(self.quote(request(raw, "openai-responses"))["amount_usd"], "0.006280")

    def test_anthropic_cache_is_additional_to_uncached_input(self):
        raw = {"input_tokens": 600, "cache_read_input_tokens": 400,
               "cache_creation_input_tokens": 100, "output_tokens": 500}
        normalized = normalize_usage(raw, "anthropic", cache_write_ttl="5m")
        self.assertEqual(normalized["input_uncached"], 600)
        self.assertEqual(normalized["input_total"], 1100)
        self.assertEqual(normalized["cache_write_5m"], 100)
        self.assertEqual(self.quote(request(raw, "anthropic", cache_write_ttl="5m"))["amount_usd"], "0.006530")

    def test_anthropic_mixed_ttls_are_exclusive_line_items(self):
        raw = {"input_tokens": 600, "cache_read_input_tokens": 400,
               "cache_creation_input_tokens": 100, "output_tokens": 500,
               "cache_creation": {"ephemeral_5m_input_tokens": 40,
                                  "ephemeral_1h_input_tokens": 60}}
        normalized = normalize_usage(raw, "anthropic")
        self.assertEqual(normalized["cache_write"], 0)
        self.assertEqual(normalized["cache_write_5m"], 40)
        self.assertEqual(normalized["cache_write_1h"], 60)
        self.assertEqual(normalized["input_total"], 1100)
        self.assertEqual(self.quote(request(raw, "anthropic"))["amount_usd"], "0.006620")

    def test_explicit_one_hour_ttl_uses_one_hour_unit_price(self):
        raw = {"input_tokens": 600, "cache_read_input_tokens": 400,
               "cache_creation_input_tokens": 100, "output_tokens": 500}
        self.assertEqual(self.quote(request(raw, "anthropic", cache_write_ttl="1h"))["amount_usd"], "0.006680")

    def test_ambiguous_or_inconsistent_cache_creation_is_rejected(self):
        raw = {"input_tokens": 600, "cache_read_input_tokens": 400,
               "cache_creation_input_tokens": 100, "output_tokens": 500}
        with self.assertRaises(CalculationError):
            self.quote(request(raw, "anthropic"))
        inconsistent = {**raw, "cache_creation": {"ephemeral_5m_input_tokens": 40,
                                                  "ephemeral_1h_input_tokens": 59}}
        with self.assertRaises(CalculationError):
            normalize_usage(inconsistent, "anthropic")

    def test_required_totals_cannot_be_silently_defaulted_to_zero(self):
        for usage_format, raw in (
            ("openai-chat", {"prompt_tokens": 1}),
            ("openai-responses", {"output_tokens": 1}),
            ("anthropic", {"input_tokens": 1}),
        ):
            with self.subTest(usage_format=usage_format), self.assertRaises(CalculationError):
                normalize_usage(raw, usage_format)

    def test_negative_boolean_fractional_and_null_counts_are_rejected(self):
        for bad in (-1, True, False, Decimal("1.5"), None):
            with self.subTest(value=bad), self.assertRaises(CalculationError):
                normalize_usage({"prompt_tokens": bad, "completion_tokens": 1}, "openai-chat")

    def test_cached_input_cannot_exceed_openai_total(self):
        with self.assertRaises(CalculationError):
            normalize_usage({"prompt_tokens": 10, "completion_tokens": 1,
                             "prompt_tokens_details": {"cached_tokens": 11}}, "openai-chat")

    def test_aliases_and_reported_totals_must_be_consistent(self):
        cases = [
            {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 12},
            {"prompt_tokens": 10, "completion_tokens": 1,
             "prompt_cache_hit_tokens": 4, "prompt_cache_miss_tokens": 6,
             "prompt_tokens_details": {"cached_tokens": 5}},
        ]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(CalculationError):
                normalize_usage(raw, "openai-chat")

    def test_unknown_positive_modalities_are_not_charged_as_text(self):
        raw = {"prompt_tokens": 10, "completion_tokens": 1,
               "prompt_tokens_details": {"audio_tokens": 1}}
        with self.assertRaises(CalculationError):
            self.quote(request(raw, "openai-chat"))

    def test_normalized_input_requires_all_six_categories(self):
        for missing in counts():
            raw = counts()
            del raw[missing]
            with self.subTest(missing=missing), self.assertRaises(CalculationError):
                normalize_usage(raw, "normalized")

    def test_generic_cache_write_cannot_overlap_duration_categories(self):
        with self.assertRaises(CalculationError):
            normalize_usage(counts(cache_write=1, cache_write_5m=1), "normalized")

    def test_published_customer_prices_are_not_discounted_twice(self):
        model = synthetic_model(official_input_price="4", official_output_price="20",
                                global_discount_rate="0.5", discount_rate="0.5")
        self.assertEqual(self.quote(model=model)["amount_usd"], "0.007000")

    def test_valid_zero_unit_prices_are_supported(self):
        result = self.quote(model=synthetic_model(customer_input_price="0", customer_output_price="0"))
        self.assertEqual(result["amount_usd"], "0.000000")

    def test_small_line_amounts_are_summed_before_rounding(self):
        result = self.quote(request(counts(input_uncached=1, output=1)),
                            synthetic_model(customer_input_price="0.4", customer_output_price="0.4"))
        self.assertEqual(Decimal(result["amount_usd_unrounded"]), Decimal("0.0000008"))
        self.assertEqual(result["amount_usd"], "0.000001")

    def test_usd_rounding_is_half_up_at_micro_dollar_boundary(self):
        for price, expected in (("0.499999", "0.000000"), ("0.5", "0.000001")):
            with self.subTest(price=price):
                result = self.quote(request(counts(input_uncached=1, output=0)),
                                    synthetic_model(customer_input_price=price))
                self.assertEqual(result["amount_usd"], expected)

    def test_cny_uses_unrounded_usd_instead_of_rounded_usd(self):
        result = self.quote(request(counts(input_uncached=1, output=0), exchange_rate="2"),
                            synthetic_model(customer_input_price="0.4"))
        self.assertEqual(result["amount_usd"], "0.000000")
        self.assertEqual(result["cny"]["amount"], "0.000001")
        self.assertEqual(result["cny"]["amount_micros"], 1)
        self.assertEqual(Decimal(result["cny"]["exchange_rate"]), Decimal("2"))

    def test_cny_is_not_inferred_when_exchange_rate_is_missing(self):
        self.assertIsNone(self.quote()["cny"])

    def test_context_below_threshold_uses_standard_price(self):
        result = self.quote(request(counts(input_uncached=99, output=0)), context_model())
        self.assertFalse(result["context_pricing"]["applied"])
        self.assertEqual(result["amount_usd"], "0.000198")

    def test_context_exactly_at_threshold_uses_standard_price(self):
        result = self.quote(request(counts(input_uncached=100, output=0)), context_model())
        self.assertFalse(result["context_pricing"]["applied"])
        self.assertEqual(result["amount_usd"], "0.000200")

    def test_context_above_threshold_multiplies_whole_request(self):
        result = self.quote(request(counts(input_uncached=101, output=0)), context_model())
        self.assertTrue(result["context_pricing"]["applied"])
        self.assertEqual(result["amount_usd"], "0.001010")

    def test_context_threshold_includes_cache_reads_and_writes(self):
        result = self.quote(request(counts(input_uncached=60, cache_read=30,
                                          cache_write_5m=20, output=10)), context_model())
        self.assertEqual(result["tokens"]["input_total"], 110)
        self.assertTrue(result["context_pricing"]["applied"])
        self.assertEqual(result["amount_usd"], "0.001380")

    def test_input_cache_and_output_use_their_own_multipliers(self):
        result = self.quote(request(counts(input_uncached=60, cache_read=41, output=20)),
                            context_model(input_factor="2", cache_factor="3", output_factor="1.5"))
        self.assertEqual(Decimal(result["amount_usd_unrounded"]), Decimal("0.0005646"))
        self.assertEqual(result["amount_usd"], "0.000565")

    def test_input_objects_are_not_mutated(self):
        value = request()
        catalog = {"items": [synthetic_model()]}
        old_value, old_catalog = copy.deepcopy(value), copy.deepcopy(catalog)
        calculate(value, catalog)
        self.assertEqual(value, old_value)
        self.assertEqual(catalog, old_catalog)

    def test_repeated_calculation_is_deterministic(self):
        value, catalog = request(), {"items": [synthetic_model()]}
        self.assertEqual(calculate(value, catalog), calculate(value, catalog))

    def test_result_has_auditable_lines_and_does_not_claim_historical_match(self):
        result = self.quote()
        self.assertEqual(result["amount_usd_micros"], 7000)
        self.assertIs(result["historical_price_match_verified"], False)
        self.assertGreaterEqual(len(result["charges"]), 2)
        for line in result["charges"]:
            self.assertTrue({"category", "tokens", "unit_price_usd_per_million",
                             "multiplier", "amount_usd_unrounded"}.issubset(line))
        self.assertEqual(sum(Decimal(line["amount_usd_unrounded"]) for line in result["charges"]),
                         Decimal(result["amount_usd_unrounded"]))

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(CalculationError):
            self.quote(request(model_id="not-in-the-catalog"))

    def test_missing_or_invalid_used_price_is_rejected(self):
        for bad in (None, "-1", "NaN", "Infinity", True):
            with self.subTest(price=bad), self.assertRaises(CalculationError):
                self.quote(model=synthetic_model(customer_input_price=bad))

    def test_image_model_and_nontext_input_are_not_silently_supported(self):
        with self.assertRaises(CalculationError):
            self.quote(model=synthetic_model(model_type="image"))
        with self.assertRaises(CalculationError):
            self.quote(request(input_modality="image"))

    def test_timestamps_must_be_valid_and_timezone_aware(self):
        for bad in ("2026-10-25T06:00:00", "not-a-time", True):
            with self.subTest(timestamp=bad), self.assertRaises(CalculationError):
                self.quote(request(request_started_at=bad))
        self.assertEqual(self.quote(request(request_started_at=START_EPOCH))["amount_usd"], "0.007000")

    def test_require_valid_quote_accepts_an_explicit_matching_window(self):
        result = self.quote(request(require_valid_quote=True), catalog_changes={
            "_metadata": {"quote_window": {"valid_from": START_EPOCH - 1,
                                           "valid_until": START_EPOCH + 1}}})
        self.assertEqual(result["amount_usd"], "0.007000")

    def test_require_valid_quote_rejects_missing_window(self):
        with self.assertRaises(CalculationError):
            self.quote(request(require_valid_quote=True))

    def test_require_valid_quote_rejects_expired_window(self):
        with self.assertRaises(CalculationError):
            self.quote(request(require_valid_quote=True), catalog_changes={
                "_metadata": {"quote_window": {"valid_from": START_EPOCH - 60,
                                               "valid_until": START_EPOCH - 1}}})

    def test_deepseek_current_quote_does_not_apply_discount_or_factor_again(self):
        result = self.quote(request(require_valid_quote=True), time_model())
        self.assertEqual(result["time_pricing"]["period"], "off_peak")
        self.assertEqual(result["amount_usd"], "0.003500")

    def test_deepseek_expired_quote_without_calendar_is_rejected(self):
        with self.assertRaises(CalculationError):
            self.quote(request(request_started_at=START_EPOCH + 61), time_model())

    def test_calendar_peak_windows_use_half_open_boundaries(self):
        cases = (
            ("08:59:59.999999", "off_peak", "0.003500"),
            ("09:00:00", "peak", "0.007000"),
            ("11:59:59.999999", "peak", "0.007000"),
            ("12:00:00", "off_peak", "0.003500"),
            ("13:59:59.999999", "off_peak", "0.003500"),
            ("14:00:00", "peak", "0.007000"),
            ("17:59:59.999999", "peak", "0.007000"),
            ("18:00:00", "off_peak", "0.003500"),
        )
        for clock, period, amount in cases:
            with self.subTest(clock=clock):
                result = calculate(
                    request(request_started_at=f"2026-10-26T{clock}+08:00"),
                    {"items": [time_model()]}, synthetic_calendar())
                self.assertEqual(result["time_pricing"]["period"], period)
                self.assertEqual(result["amount_usd"], amount)
                self.assertIs(result["historical_price_match_verified"], False)

    def test_weekends_stay_off_peak_including_a_makeup_saturday(self):
        # The first date represents a make-up-work Saturday scenario. It is not
        # a holiday in this synthetic fixture: the weekend rule alone applies.
        for day in ("2026-02-14", "2026-02-15"):
            with self.subTest(day=day):
                self.assertGreaterEqual(datetime.fromisoformat(day).weekday(), 5)
                result = calculate(request(request_started_at=day + "T10:00:00+08:00"),
                                   {"items": [time_model()]}, synthetic_calendar())
                self.assertEqual(result["time_pricing"]["period"], "off_peak")
                self.assertEqual(result["time_pricing"]["reason"], "weekend")
                self.assertEqual(result["amount_usd"], "0.003500")

    def test_calendar_holiday_overrides_weekday_peak_hours(self):
        day = "2026-10-01"
        self.assertLess(datetime.fromisoformat(day).weekday(), 5)
        result = calculate(request(request_started_at=day + "T10:00:00+08:00"),
                           {"items": [time_model()]}, synthetic_calendar())
        self.assertEqual(result["time_pricing"]["period"], "off_peak")
        self.assertEqual(result["time_pricing"]["reason"], "holiday")

    def test_calendar_does_not_guess_an_uncovered_year(self):
        with self.assertRaises(CalculationError):
            calculate(request(request_started_at="2027-10-26T10:00:00+08:00"),
                      {"items": [time_model()]}, synthetic_calendar())

    def test_calendar_and_rule_versions_must_match_price_metadata(self):
        for field in ("version", "rule_version"):
            with self.subTest(field=field):
                calendar = synthetic_calendar()
                calendar[field] = "incompatible-version"
                with self.assertRaises(CalculationError):
                    calculate(request(request_started_at="2026-10-26T10:00:00+08:00"),
                              {"items": [time_model()]}, calendar)

    def test_calendar_timezone_offset_and_weekend_rule_are_explicit(self):
        for changes in ({"timezone": "UTC"}, {"utc_offset_minutes": 0},
                        {"weekends_off_peak": False}):
            with self.subTest(changes=changes):
                calendar = synthetic_calendar()
                calendar.update(changes)
                with self.assertRaises(CalculationError):
                    calculate(request(request_started_at="2026-10-26T10:00:00+08:00"),
                              {"items": [time_model()]}, calendar)

    def test_complete_request_uses_start_tier_even_near_period_end(self):
        tokens = counts(input_uncached=1000, output=10000)
        before = calculate(request(tokens, request_started_at="2026-10-26T11:59:59+08:00"),
                           {"items": [time_model()]}, synthetic_calendar())
        after = calculate(request(tokens, request_started_at="2026-10-26T12:00:00+08:00"),
                          {"items": [time_model()]}, synthetic_calendar())
        self.assertEqual(before["time_pricing"]["price_basis"], "request_start")
        self.assertEqual(before["time_pricing"]["period"], "peak")
        self.assertEqual(before["amount_usd"], "0.102000")
        self.assertEqual(after["time_pricing"]["period"], "off_peak")
        self.assertEqual(after["amount_usd"], "0.051000")

    def test_time_period_is_selected_in_beijing_not_input_offset(self):
        for timestamp in ("2026-10-26T09:00:00+08:00", "2026-10-26T01:00:00Z",
                          "2026-10-26T10:00:00+09:00"):
            with self.subTest(timestamp=timestamp):
                result = calculate(request(request_started_at=timestamp),
                                   {"items": [time_model()]}, synthetic_calendar())
                self.assertEqual(result["time_pricing"]["period"], "peak")
                self.assertEqual(result["amount_usd"], "0.007000")

    def test_calendar_input_is_not_mutated(self):
        calendar = synthetic_calendar()
        previous = copy.deepcopy(calendar)
        calculate(request(request_started_at="2026-10-26T10:00:00+08:00"),
                  {"items": [time_model()]}, calendar)
        self.assertEqual(calendar, previous)

    def test_calendar_cannot_silently_override_conflicting_valid_quote(self):
        model = time_model()
        at_peak = "2026-10-26T10:00:00+08:00"
        epoch = int(datetime.fromisoformat(at_peak).timestamp())
        model["time_pricing"]["quoted_at"] = epoch
        model["time_pricing"]["valid_until"] = epoch + 60
        # The supplied quote still claims off-peak, contrary to its calendar.
        with self.assertRaises(CalculationError):
            calculate(request(request_started_at=at_peak), {"items": [model]},
                      synthetic_calendar())

    def test_missing_selected_time_tier_does_not_fall_back_to_current_price(self):
        model = time_model()
        del model["time_pricing"]["tiers"]["peak"]
        with self.assertRaises(CalculationError):
            calculate(request(request_started_at="2026-10-26T10:00:00+08:00"),
                      {"items": [model]}, synthetic_calendar())

    def test_selected_time_tier_cache_write_price_overrides_top_level(self):
        model = time_model()
        model["customer_cache_write_price"] = "2.5"
        model["time_pricing"]["tiers"]["peak"]["customer_cache_write_price"] = "7"
        value = request(counts(input_uncached=0, cache_write_5m=1000, output=0),
                        request_started_at="2026-10-26T10:00:00+08:00")
        result = calculate(value, {"items": [model]}, synthetic_calendar())
        self.assertEqual(result["amount_usd"], "0.007000")
        line = next(item for item in result["charges"] if item["category"] == "cache_write_5m")
        self.assertEqual(Decimal(line["unit_price_usd_per_million"]), Decimal("7"))

    def test_missing_selected_time_tier_write_price_cannot_use_top_level(self):
        for category in ("cache_write_5m", "cache_write_1h"):
            with self.subTest(category=category):
                model = time_model()
                value = request(counts(input_uncached=0, output=0, **{category: 1000}),
                                request_started_at="2026-10-26T10:00:00+08:00")
                with self.assertRaises(CalculationError):
                    calculate(value, {"items": [model]}, synthetic_calendar())

    def test_price_currency_must_be_usd(self):
        for currency in ("CNY", "EUR", "usd", None):
            with self.subTest(currency=currency), self.assertRaises(CalculationError):
                self.quote(catalog_changes={"_metadata": {"currency": currency}})

    def test_price_unit_must_be_per_million_tokens(self):
        for unit in ("USD_per_thousand_tokens", "USD_per_token", "CNY_per_million_tokens", None):
            with self.subTest(unit=unit), self.assertRaises(CalculationError):
                self.quote(catalog_changes={"_metadata": {"price_unit": unit}})

    def test_json_prices_are_parsed_as_decimal(self):
        parsed = load_json('{"price": 0.095, "tokens": 1000}')
        self.assertIsInstance(parsed["price"], Decimal)
        self.assertEqual(parsed["price"], Decimal("0.095"))
        self.assertEqual(parsed["tokens"], 1000)

    def test_json_duplicate_keys_are_rejected_even_when_nested(self):
        for text in ('{"a":1,"a":2}', '{"outer":{"a":1,"a":2}}'):
            with self.subTest(text=text), self.assertRaises(CalculationError):
                load_json(text)

    def test_json_nonfinite_constants_are_rejected(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token), self.assertRaises(CalculationError):
                load_json('{"price":' + token + '}')

    def test_explicit_zero_usage_returns_zero_not_missing_usage(self):
        result = self.quote(request(counts(input_uncached=0, output=0)))
        self.assertEqual(result["amount_usd"], "0.000000")
        self.assertEqual(result["amount_usd_micros"], 0)

    def test_hostile_decimal_context_does_not_change_numeric_unix_timestamp(self):
        stamp = Decimal(START_EPOCH) + Decimal("0.125")
        value = request(request_started_at=stamp, exchange_rate="6.831234")
        catalog = {"items": [synthetic_model()]}
        expected = calculate(value, catalog)
        with localcontext() as caller:
            caller.prec = 2
            caller.Emax = 1
            caller.Emin = -1
            caller.rounding = ROUND_DOWN
            caller.traps[Inexact] = True
            caller.traps[Rounded] = True
            actual = calculate(value, catalog)
        self.assertEqual(actual, expected)

    def test_hostile_decimal_context_cannot_change_money_or_rounding(self):
        value = request(counts(input_uncached=1234567, output=2345678), exchange_rate="6.831234")
        catalog = {"items": [synthetic_model(
            customer_input_price="2.12345678901234567890123456789",
            customer_output_price="10.9876543210987654321098765432")]}
        expected = calculate(value, catalog)
        with localcontext() as caller:
            caller.prec = 2
            caller.Emax = 1
            caller.Emin = -1
            caller.rounding = ROUND_FLOOR
            caller.traps[Inexact] = True
            caller.traps[Rounded] = True
            actual = calculate(value, catalog)
        self.assertEqual(actual, expected)

    def test_calculation_preserves_the_callers_decimal_context_and_flags(self):
        with localcontext() as caller:
            caller.prec = 3
            caller.rounding = ROUND_DOWN
            caller.traps[Inexact] = True
            caller.traps[Rounded] = True
            caller.clear_flags()
            previous = caller.copy()
            self.quote(request(counts(input_uncached=1, output=1)),
                       synthetic_model(customer_input_price="0.4", customer_output_price="0.4"))
            for name in ("prec", "rounding", "Emax", "Emin", "capitals", "clamp"):
                self.assertEqual(getattr(caller, name), getattr(previous, name))
            self.assertEqual(caller.traps, previous.traps)
            self.assertEqual(caller.flags, previous.flags)

    def test_calculator_imports_only_the_reviewed_standard_library_modules(self):
        source = Path(__file__).with_name("calculator.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name, ALLOWED_IMPORTS)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertIn(node.module, ALLOWED_IMPORTS)

    def test_module_body_import_has_no_runtime_file_environment_or_network_io(self):
        path = Path(__file__).with_name("calculator.py")
        # Loading the reviewed source itself is outside the runtime-I/O guard.
        code = compile(path.read_text(), str(path), "exec")
        namespace = {"__name__": "calculator_isolation_probe", "__file__": str(path)}
        with no_runtime_io():
            exec(code, namespace)
        self.assertTrue(callable(namespace["calculate"]))

    def test_pure_calculation_has_no_file_environment_or_network_io(self):
        value, catalog = request(), {"items": [synthetic_model()]}
        with no_runtime_io():
            result = calculate(value, catalog)
        self.assertEqual(result["amount_usd"], "0.007000")

    def test_numeric_quotes_preserve_submicrosecond_window_boundaries(self):
        model = time_model()
        begin = Decimal(START_EPOCH) + Decimal("0.0000006")
        end = Decimal(START_EPOCH) + Decimal("0.0000008")
        model["time_pricing"].update(quoted_at=begin, valid_until=end)
        value = request(request_started_at=Decimal(START_EPOCH) + Decimal("0.0000007"),
                        require_valid_quote=True)
        result = self.quote(value, model)
        self.assertTrue(result["time_pricing"]["within_supplied_quote_window"])
        self.assertEqual(result["request_started_at_epoch"], str(value["request_started_at"]))
        value["request_started_at"] = end
        with self.assertRaises(CalculationError) as caught:
            self.quote(value, model)
        self.assertEqual(caught.exception.code, "quote_out_of_window")

    def test_numeric_timestamp_does_not_round_up_across_a_peak_boundary(self):
        peak_epoch = int(datetime.fromisoformat("2026-10-26T09:00:00+08:00").timestamp())
        before = Decimal(peak_epoch) - Decimal("0.0000001")
        result = calculate(request(request_started_at=before),
                           {"items": [time_model()]}, synthetic_calendar())
        self.assertEqual(result["time_pricing"]["period"], "off_peak")
        self.assertTrue(result["time_pricing"]["request_started_at_local"].endswith("08:59:59.999999+08:00"))

    def test_negative_numeric_timestamp_floors_display_to_microseconds(self):
        result = self.quote(request(request_started_at=Decimal("-0.0000001")))
        self.assertEqual(result["request_started_at"], "1969-12-31T23:59:59.999999+00:00")
        self.assertEqual(result["request_started_at_epoch"], "-0.0000001")

    def test_timestamp_precision_is_checked_instead_of_silently_rounded(self):
        for stamp in ("2026-10-25T06:00:00.1234567+08:00", Decimal("1e-31"),
                      Decimal("1792879792.12345678901234567890123")):
            with self.subTest(stamp=stamp), self.assertRaises(CalculationError) as caught:
                self.quote(request(request_started_at=stamp))
            self.assertEqual(caught.exception.code, "unsupported_timestamp_precision")
        result = self.quote(request(request_started_at="2026-10-25T06:00:00.123456+08:00"))
        self.assertEqual(result["request_started_at"], "2026-10-24T22:00:00.123456+00:00")

    def test_zero_price_with_large_exponent_is_canonicalized(self):
        result = self.quote(model=synthetic_model(customer_input_price="0E+100000000000",
                                                customer_output_price="0E-100000000000"))
        self.assertEqual(result["amount_usd"], "0.000000")

    def test_shipped_synthetic_examples_with_public_price_snapshot(self):
        directory = Path(__file__).parent
        catalog = load_json((directory / "public-prices-2026-10-25.json").read_text())
        calendar = load_json((directory / "calendar-2026.json").read_text())
        for filename, rounded, exact in (
            ("anthropic-cache.json", "0.007543", "0.007543"),
            ("gpt-long-context.json", "0.016258", "0.016258176"),
            ("deepseek-off-peak.json", "0.001721", "0.0017206541"),
        ):
            with self.subTest(filename=filename):
                value = load_json((directory / "examples" / filename).read_text())
                result = calculate(value, catalog, calendar)
                self.assertEqual(result["amount_usd"], rounded)
                self.assertEqual(Decimal(result["amount_usd_unrounded"]), Decimal(exact))
                self.assertIs(result["historical_price_match_verified"], False)


if __name__ == "__main__":
    unittest.main()
