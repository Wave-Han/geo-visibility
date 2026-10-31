# CLI entry: collect / parse / report
#   collect --pilot          small pilot (3 brands x 18 questions) -> output/raw_pilot/
#   collect --pilot --brands "A,B,C"   pilot with custom brands
#   collect                  full run -> output/raw/
#   parse [--dir raw_pilot]  heuristic-parse raw answers into output/parsed.json
#   report [--dir raw_pilot] render output/summary.html + console digest
import argparse
import asyncio
import json

from . import analysis, config, collector, parser, report
from .questions import load_brands


def main() -> None:
    ap = argparse.ArgumentParser(prog="geo_visibility")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub_collect = sub.add_parser("collect")
    sub_collect.add_argument("--pilot", action="store_true",
                             help="small pilot run into output/raw_pilot/")
    sub_collect.add_argument("--brands", default=None,
                             help="comma-separated brand names (pilot mode only)")

    sub_parse = sub.add_parser("parse")
    sub_parse.add_argument("--dir", default="raw", help="subdir of output/")
    sub_parse.add_argument("--llm", action="store_true",
                           help="use DeepSeek LLM parsing (sentiment/verdict); "
                                "needs DEEPSEEK_API_KEY, falls back per record")

    sub_report = sub.add_parser("report")
    sub_report.add_argument("--dir", default="raw", help="subdir of output/")

    sub_full = sub.add_parser("full-report")
    sub_full.add_argument("--dir", default="raw", help="subdir of output/")

    sub_one = sub.add_parser("onepager")
    sub_one.add_argument("--names", required=True,
                         help="comma-separated brand names, e.g. Narwal,UWANT")
    sub_one.add_argument("--dir", default="raw", help="subdir of output/")

    args = ap.parse_args()

    cfg = config.load_config()
    brands = load_brands(cfg["brands"])
    matchers = parser.build_matchers(brands)

    def run_parse(records):
        llm_call = None
        if args.cmd == "parse" and args.llm:
            import os
            key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not key:
                raise SystemExit("--llm needs DEEPSEEK_API_KEY (see README)")
            from .llm import make_deepseek_llm_call
            llm_call = make_deepseek_llm_call(key)
            print("LLM parsing via deepseek-chat (heuristic fallback per record)")
        return asyncio.run(parser.parse_all(records, matchers, llm_call))

    def load_parsed(records):
        """Deterministic mentions (regex) + LLM semantics from persisted parse."""
        base = [parser.parse_record_heuristic(r, matchers)
                for r in records if r.get("answer") and not r.get("error")]
        parsed_path = config.OUTPUT_DIR / f"parsed_{args.dir}.json"
        if parsed_path.exists():
            sem = parser.parsed_from_json(
                json.loads(parsed_path.read_text(encoding="utf-8")))
            print(f"using persisted LLM semantics: {parsed_path} "
                  f"(mentions stay regex-based; re-run 'parse --llm' to refresh)")
            return parser.merge_semantics(base, sem)
        print("no persisted LLM parse - verdicts/quotes will be thin; "
              "run 'parse --llm' first")
        return base

    if args.cmd == "collect":
        raw_dir = config.OUTPUT_DIR / ("raw_pilot" if args.pilot else "raw")
        pilot_brands = args.brands.split(",") if args.brands else None
        asyncio.run(collector.collect(cfg, raw_dir,
                                      pilot=args.pilot, pilot_brands=pilot_brands))

    elif args.cmd == "parse":
        records = collector.load_records(config.OUTPUT_DIR / args.dir)
        parsed = run_parse(records)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = config.OUTPUT_DIR / f"parsed_{args.dir}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump([p.__dict__ for p in parsed], f, ensure_ascii=False,
                      default=lambda o: o.__dict__)
        print(f"parsed {len(parsed)} answers -> {out}")

    elif args.cmd == "report":
        records = collector.load_records(config.OUTPUT_DIR / args.dir)
        parsed = load_parsed(records)
        html = report.render_summary_html(brands, parsed, records)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = config.OUTPUT_DIR / f"summary_{args.dir}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"report -> {out}")
        # quick console digest
        for tier, rate in analysis.tier_comparison(brands, parsed).items():
            print(f"tier={tier} avg mention rate={rate:.0%}")
        for country, rate in analysis.country_comparison(brands, parsed).items():
            print(f"country={country} avg mention rate={rate:.0%}")

    elif args.cmd == "full-report":
        from . import report_v1
        records = collector.load_records(config.OUTPUT_DIR / args.dir)
        parsed = load_parsed(records)
        html = report_v1.generate_report(brands, parsed, records)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = config.OUTPUT_DIR / f"report_v1_{args.dir}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"full report -> {out}")

    elif args.cmd == "onepager":
        from . import report_v1
        records = collector.load_records(config.OUTPUT_DIR / args.dir)
        parsed = load_parsed(records)
        by_name = {b.name: b for b in brands}
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name in [n.strip() for n in args.names.split(",") if n.strip()]:
            brand = by_name.get(name)
            if not brand:
                print(f"SKIP {name}: not in brands.yaml")
                continue
            out = config.OUTPUT_DIR / f"onepager_{brand.name.lower().replace(' ', '-')}.html"
            with open(out, "w", encoding="utf-8") as f:
                f.write(report_v1.generate_brand_onepager(brand, parsed, records))
            print(f"onepager -> {out}")


if __name__ == "__main__":
    main()
