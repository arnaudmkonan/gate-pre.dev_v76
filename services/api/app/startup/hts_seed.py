"""Seed starter USITC HTS tariff codes and CSV import utility."""

import argparse
import asyncio
import csv
import logging
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Tuple

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal
from app.models.reference_data import HTSCode

logger = logging.getLogger(__name__)

# (hts_code, description, chapter, duty_rate_label, duty_rate_percent)
STARTER_USITC_HTS_CODES: Tuple[Tuple[str, str, int, str, str], ...] = (
    ("0702.00.2000", "Tomatoes, fresh or chilled, imported Mar 1 to Jul 14 or Sep 1 to Nov 14", 7, "3.9¢/kg", "2.8000"),
    ("0804.40.0000", "Avocados, fresh or dried", 8, "11.2¢/kg", "4.5000"),
    ("0901.21.0030", "Coffee, roasted, not decaffeinated, in retail containers <= 2 kg", 9, "Free", "0.0000"),
    ("2204.21.5060", "Wine of fresh grapes, in containers holding 2 liters or less, >14% vol", 22, "6.3¢/liter", "1.5000"),
    ("3004.90.9290", "Medicaments put up in measured doses or packings for retail sale, NESOI", 30, "Free", "0.0000"),
    ("3304.99.5000", "Beauty or make-up preparations and preparations for care of the skin, NESOI", 33, "Free", "0.0000"),
    ("3923.10.9000", "Boxes, cases, crates and similar articles for conveyance or packing, of plastics", 39, "3%", "3.0000"),
    ("3926.90.9985", "Other articles of plastics and articles of other materials of headings 3901-3914", 39, "5.3%", "5.3000"),
    ("4202.22.8100", "Handbags with outer surface of man-made textile materials", 42, "17.6%", "17.6000"),
    ("4202.92.3120", "Travel, sports and similar backpacks with outer surface of man-made fibers", 42, "17.6%", "17.6000"),
    ("4819.10.0040", "Cartons, boxes and cases, of corrugated paper or paperboard", 48, "Free", "0.0000"),
    ("6109.10.0012", "Men's or boys' T-shirts, singlets, tank tops, knitted or crocheted, of cotton", 61, "16.5%", "16.5000"),
    ("6110.20.2069", "Sweaters, pullovers, sweatshirts, waistcoats, knitted or crocheted, of cotton", 61, "16.5%", "16.5000"),
    ("6110.30.3059", "Sweaters, pullovers, sweatshirts, knitted or crocheted, of man-made fibers", 61, "32%", "32.0000"),
    ("6203.42.4511", "Men's or boys' trousers and breeches, not knitted, of cotton (blue denim)", 62, "16.6%", "16.6000"),
    ("6204.62.8011", "Women's or girls' trousers and breeches, not knitted, of cotton", 62, "16.6%", "16.6000"),
    ("6302.31.9020", "Bed linen, not knitted or crocheted, of cotton, not printed, NESOI", 63, "6.7%", "6.7000"),
    ("6402.99.3165", "Other footwear with outer soles and uppers of rubber or plastics, women's", 64, "6%", "6.0000"),
    ("6403.99.6075", "Footwear with outer soles of rubber/plastics and uppers of leather, men's", 64, "8.5%", "8.5000"),
    ("6404.11.9020", "Sports/athletic footwear with outer soles of rubber/plastics and textile uppers", 64, "20%", "20.0000"),
    ("6912.00.4810", "Ceramic tableware and kitchenware, other than of porcelain or china", 69, "9.8%", "9.8000"),
    ("7013.49.5040", "Glassware of a kind used for table or kitchen purposes, valued > $3 each", 70, "7.2%", "7.2000"),
    ("7318.15.8065", "Other screws and bolts, threaded, of iron or steel, having shanks >= 6 mm", 73, "8.5%", "8.5000"),
    ("7323.93.0060", "Cooking and kitchenware of stainless steel", 73, "2%", "2.0000"),
    ("7326.90.8688", "Other articles of iron or steel, NESOI", 73, "2.9%", "2.9000"),
    ("7616.99.5190", "Other articles of aluminum, NESOI", 76, "2.5%", "2.5000"),
    ("8414.51.9090", "Table, floor, wall, window, ceiling or roof fans with self-contained motor <= 125W", 84, "4.7%", "4.7000"),
    ("8415.10.6000", "Window or wall type air conditioning machines, split-system", 84, "1.4%", "1.4000"),
    ("8421.21.0000", "Filtering or purifying machinery and apparatus for water", 84, "Free", "0.0000"),
    ("8428.90.0390", "Other lifting, handling, loading or unloading machinery, NESOI", 84, "Free", "0.0000"),
    ("8471.30.0100", "Portable automatic data processing machines <= 10 kg, with CPU, keyboard & display", 84, "Free", "0.0000"),
    ("8471.50.0150", "Processing units other than those of subheading 8471.41 or 8471.49", 84, "Free", "0.0000"),
    ("8473.30.1180", "Printed circuit assemblies, parts and accessories of ADP machines of 8471", 84, "Free", "0.0000"),
    ("8479.89.9599", "Machines and mechanical appliances having individual functions, NESOI", 84, "2.5%", "2.5000"),
    ("8481.80.9050", "Taps, cocks, valves and similar appliances for pipes, boiler shells, tanks, NESOI", 84, "2%", "2.0000"),
    ("8501.10.4060", "Electric motors of an output not exceeding 37.5 W, DC, brushless", 85, "4.4%", "4.4000"),
    ("8504.40.8500", "Static converters (power supplies) for telecommunication apparatus", 85, "Free", "0.0000"),
    ("8504.40.9550", "Rectifiers and rectifying apparatus, power supplies, NESOI", 85, "Free", "0.0000"),
    ("8507.60.0020", "Lithium-ion electric storage batteries", 85, "3.4%", "3.4000"),
    ("8517.13.0000", "Smartphones for cellular networks or for other wireless networks", 85, "Free", "0.0000"),
    ("8517.62.0050", "Machines for the reception, conversion and transmission of voice, images or data", 85, "Free", "0.0000"),
    ("8518.30.2000", "Headphones and earphones, whether or not combined with microphone", 85, "Free", "0.0000"),
    ("8528.52.0000", "Monitors capable of directly connecting to and designed for ADP machines of 8471", 85, "Free", "0.0000"),
    ("8536.69.4040", "Coaxial connectors, cylindrical multicontact connectors, rack and panel connectors", 85, "Free", "0.0000"),
    ("8541.43.0010", "Photovoltaic cells assembled in modules or made up into panels, crystalline silicon", 85, "Free", "0.0000"),
    ("8542.31.0001", "Electronic integrated circuits: processors and controllers", 85, "Free", "0.0000"),
    ("8544.42.9090", "Other electric conductors, for a voltage <= 1,000 V, fitted with connectors", 85, "2.6%", "2.6000"),
    ("8708.29.5160", "Other parts and accessories of bodies (including cabs) for motor vehicles", 87, "2.5%", "2.5000"),
    ("8708.30.5090", "Brakes and servo-brakes and parts thereof for motor vehicles, NESOI", 87, "2.5%", "2.5000"),
    ("8711.60.0050", "Cycles fitted with an electric motor for propulsion <= 250 W (e-bikes)", 87, "Free", "0.0000"),
    ("9018.90.8000", "Instruments and appliances used in medical, surgical, dental or veterinary sciences", 90, "Free", "0.0000"),
    ("9031.80.8085", "Measuring or checking instruments, appliances and machines, NESOI", 90, "Free", "0.0000"),
    ("9401.39.0010", "Swivel seats with variable height adjustment, other than of wood, household", 94, "Free", "0.0000"),
    ("9403.20.0050", "Other metal furniture, household", 94, "Free", "0.0000"),
    ("9403.60.8081", "Other wooden furniture, NESOI", 94, "Free", "0.0000"),
    ("9405.42.8440", "Other electric luminaires and lighting fittings designed for LED light sources", 94, "3.9%", "3.9000"),
    ("9503.00.0090", "Tricycles, scooters, pedal cars and similar wheeled toys; dolls; other toys", 95, "Free", "0.0000"),
)


async def seed_starter_hts_codes_if_empty() -> int:
    """Populate starter USITC HTS rows when hts_codes table is empty."""
    async with AsyncSessionLocal() as session:
        count_res = await session.execute(select(func.count()).select_from(HTSCode))
        existing = count_res.scalar() or 0
        if existing > 0:
            return 0

        inserted = await _upsert_hts_rows(session, STARTER_USITC_HTS_CODES)
        await session.commit()
        logger.info("Seeded %s starter USITC HTS tariff codes", inserted)
        return inserted


async def _upsert_hts_rows(
    session,
    rows: Iterable[Tuple[str, str, int, str, str]],
) -> int:
    seq_res = await session.execute(text("SELECT pg_get_serial_sequence('hts_codes', 'id')"))
    seq_name = seq_res.scalar()
    if seq_name:
        max_res = await session.execute(text("SELECT MAX(id) FROM hts_codes"))
        max_id = max_res.scalar()
        if max_id is not None:
            await session.execute(
                text("SELECT setval(:seq, :val, true)"),
                {"seq": seq_name, "val": int(max_id)},
            )

    inserted = 0
    stmt = text(
        """
        INSERT INTO hts_codes (hts_code, description, chapter, duty_rate, duty_rate_percent)
        VALUES (:hts_code, :description, :chapter, :duty_rate, :duty_rate_percent)
        ON CONFLICT (hts_code) DO UPDATE SET
            description = EXCLUDED.description,
            chapter = EXCLUDED.chapter,
            duty_rate = EXCLUDED.duty_rate,
            duty_rate_percent = EXCLUDED.duty_rate_percent
        """
    )
    for code, desc, chapter, rate_str, rate_pct in rows:
        await session.execute(
            stmt,
            {
                "hts_code": code.strip(),
                "description": desc.strip(),
                "chapter": int(chapter),
                "duty_rate": rate_str.strip(),
                "duty_rate_percent": Decimal(str(rate_pct)),
            },
        )
        inserted += 1
    return inserted


async def import_usitc_csv(csv_path: Path) -> int:
    """Import USITC HTS export CSV (columns: HTS Number / hts_code, Description, General Rate of Duty)."""
    parsed_rows = []
    with csv_path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = (
                row.get("HTS Number")
                or row.get("hts_code")
                or row.get("htsno")
                or ""
            ).strip()
            desc = (row.get("Description") or row.get("description") or "").strip()
            digits = "".join(c for c in code if c.isdigit())
            if len(digits) < 6 or not desc:
                continue
            rate_label = (
                row.get("General Rate of Duty")
                or row.get("duty_rate")
                or row.get("general")
                or "Free"
            ).strip()
            pct = "0.0000"
            if "%" in rate_label:
                num_part = "".join(
                    c for c in rate_label.split("%", 1)[0] if c.isdigit() or c == "."
                )
                if num_part:
                    pct = num_part
            parsed_rows.append((code, desc, int(digits[:2]), rate_label or "Free", pct))

    async with AsyncSessionLocal() as session:
        count = await _upsert_hts_rows(session, parsed_rows)
        await session.commit()
    return count


def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed or import USITC HTS tariff schedule into hts_codes")
    parser.add_argument("--csv", type=Path, help="Optional USITC HTS CSV file to import")
    args = parser.parse_args()

    if args.csv:
        loaded = asyncio.run(import_usitc_csv(args.csv))
        print(f"Imported {loaded} USITC HTS rows from {args.csv}")
    else:
        loaded = asyncio.run(seed_starter_hts_codes_if_empty())
        print(f"Seeded {loaded} starter USITC HTS rows")


if __name__ == "__main__":
    _main()
