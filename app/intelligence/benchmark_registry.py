from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkDefinition:
    symbol: str
    name: str
    benchmark_type: str
    sectors: tuple[str, ...] = ()


class BenchmarkRegistry:
    """Central registry for benchmark instruments used by replay and ranking."""

    DEFAULT = BenchmarkDefinition(
        symbol="^NSEI",
        name="NIFTY 50",
        benchmark_type="MARKET",
    )

    SECTOR_BENCHMARKS = (
        BenchmarkDefinition("^CNXIT", "NIFTY IT", "SECTOR", ("IT", "Information Technology")),
        BenchmarkDefinition("^CNXPHARMA", "NIFTY Pharma", "SECTOR", ("Pharma", "Healthcare")),
        BenchmarkDefinition("^CNXMETAL", "NIFTY Metal", "SECTOR", ("Metals", "Metal")),
        BenchmarkDefinition("^CNXAUTO", "NIFTY Auto", "SECTOR", ("Auto", "Automobile")),
        BenchmarkDefinition("^CNXENERGY", "NIFTY Energy", "SECTOR", ("Energy", "Oil & Gas")),
        BenchmarkDefinition("^CNXPSUBANK", "NIFTY PSU Bank", "SECTOR", ("Banking", "Financial Services")),
        BenchmarkDefinition("^CNXREALTY", "NIFTY Realty", "SECTOR", ("Realty", "Real Estate")),
        BenchmarkDefinition("^CNXFMCG", "NIFTY FMCG", "SECTOR", ("FMCG", "Consumer Staples")),
    )

    @classmethod
    def select(cls, sector: str | None) -> BenchmarkDefinition:
        normalized = (sector or "").strip().lower()
        for benchmark in cls.SECTOR_BENCHMARKS:
            if any(value.lower() in normalized or normalized in value.lower() for value in benchmark.sectors):
                return benchmark
        return cls.DEFAULT

    @classmethod
    def all(cls) -> list[BenchmarkDefinition]:
        return [cls.DEFAULT, *cls.SECTOR_BENCHMARKS]
