"""
Compliance Scorecard Service
Calculate importer compliance scores, trends, and risk rankings.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def calculate_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


class ComplianceScorecardService:
    """Service for calculating compliance scores and trends."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_importer_score(
        self,
        importer_name: str = None,
        importer_id: str = None,
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Calculate compliance score for an importer.
        
        Scoring is based on:
        - Classification accuracy (30% weight)
        - Valuation accuracy (25% weight)
        - Country of origin accuracy (15% weight)
        - Sanctions screening (20% weight)
        - Documentation completeness (10% weight)
        
        Args:
            importer_name: Importer name to score
            importer_id: Importer ID to score
            period_days: Analysis period in days
            
        Returns:
            Compliance score with breakdown
        """
        from app.models.reference_data import ComplianceScreen
        from app.models.ace_entry import ACEEntry
        
        period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Initialize score structure
        score = {
            "entity_name": importer_name or "All Importers",
            "entity_id": importer_id,
            "period_start": period_start.strftime("%Y-%m-%d"),
            "period_end": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_entries_analyzed": 0,
            "total_errors_found": 0,
            "error_rate": 0.0,
            
            # Category scores
            "classification_score": 100.0,
            "valuation_score": 100.0,
            "origin_score": 100.0,
            "sanctions_score": 100.0,
            "documentation_score": 100.0,
            
            # Error counts
            "classification_errors": 0,
            "valuation_errors": 0,
            "origin_errors": 0,
            "sanctions_flags": 0,
            "documentation_errors": 0,
            
            # Financial
            "total_value_analyzed": 0.0,
            "total_duty_analyzed": 0.0,
            "total_duty_discrepancy": 0.0,
            "potential_penalties": 0.0,
            
            # Overall
            "overall_score": 100.0,
            "grade": "A",
            "score_trend": "stable"
        }
        
        try:
            # Get ACE entries for this importer
            entry_query = select(ACEEntry).where(
                ACEEntry.created_at >= period_start
            )
            
            if importer_name:
                entry_query = entry_query.where(
                    ACEEntry.importer_name.ilike(f"%{importer_name}%")
                )
            
            result = await self.db.execute(entry_query)
            entries = result.scalars().all()
            
            score["total_entries_analyzed"] = len(entries)
            
            if entries:
                score["total_value_analyzed"] = sum(
                    float(e.entered_value or 0) for e in entries
                )
                score["total_duty_analyzed"] = sum(
                    float(e.duty_amount or 0) for e in entries
                )
            
            # Get compliance screens
            screen_query = select(ComplianceScreen).where(
                ComplianceScreen.created_at >= period_start
            )
            
            result = await self.db.execute(screen_query)
            screens = result.scalars().all()
            
            # Count errors by type
            for screen in screens:
                screen_type = screen.screen_type or ""
                risk_level = screen.risk_level or ""
                
                if screen_type == "adcvd" and risk_level != "clear":
                    score["classification_errors"] += 1
                elif screen_type in ["section_301", "section_232"]:
                    if risk_level in ["high", "confirmed_match"]:
                        score["valuation_errors"] += 1
                elif screen_type == "ofac":
                    if risk_level == "confirmed_match":
                        score["sanctions_flags"] += 3
                    elif risk_level == "possible_match":
                        score["sanctions_flags"] += 1
            
            # Calculate category scores
            total = score["total_entries_analyzed"] or 1
            
            # Classification: 20% error rate = 0 score
            class_rate = score["classification_errors"] / total
            score["classification_score"] = max(0, round(100 - (class_rate * 500), 1))
            
            # Valuation: 20% error rate = 0 score
            val_rate = score["valuation_errors"] / total
            score["valuation_score"] = max(0, round(100 - (val_rate * 500), 1))
            
            # Origin: 20% error rate = 0 score
            origin_rate = score["origin_errors"] / total
            score["origin_score"] = max(0, round(100 - (origin_rate * 500), 1))
            
            # Sanctions: any confirmed match is severe
            if score["sanctions_flags"] > 0:
                score["sanctions_score"] = max(0, 100 - (score["sanctions_flags"] * 20))
            
            # Documentation: less penalty
            doc_rate = score["documentation_errors"] / total
            score["documentation_score"] = max(0, round(100 - (doc_rate * 300), 1))
            
            # Calculate overall weighted score
            weights = {
                "classification": 0.30,
                "valuation": 0.25,
                "origin": 0.15,
                "sanctions": 0.20,
                "documentation": 0.10
            }
            
            score["overall_score"] = round(
                score["classification_score"] * weights["classification"] +
                score["valuation_score"] * weights["valuation"] +
                score["origin_score"] * weights["origin"] +
                score["sanctions_score"] * weights["sanctions"] +
                score["documentation_score"] * weights["documentation"],
                1
            )
            
            score["grade"] = calculate_grade(score["overall_score"])
            
            # Error totals
            score["total_errors_found"] = (
                score["classification_errors"] +
                score["valuation_errors"] +
                score["origin_errors"] +
                score["documentation_errors"]
            )
            
            if total > 0:
                score["error_rate"] = round(
                    (score["total_errors_found"] / total) * 100, 2
                )
            
            # Estimate penalties (2x duty loss for negligence)
            score["potential_penalties"] = score["total_duty_discrepancy"] * 2
            
        except Exception as e:
            logger.error(f"Error calculating compliance score: {e}")
            score["overall_score"] = 0
            score["grade"] = "N/A"
        
        return score
    
    async def get_compliance_trends(self, months: int = 12) -> Dict[str, Any]:
        """
        Get compliance trends over time.
        
        Returns monthly scores, error trends, and risk breakdowns.
        """
        from app.models.ace_entry import ACEEntry
        from app.models.reference_data import ComplianceScreen
        
        trends = {
            "monthly_scores": [],
            "risk_type_breakdown": [],
            "risk_level_breakdown": [],
            "importer_breakdown": []
        }
        
        try:
            # Get all entries grouped by month
            cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
            
            entry_query = select(ACEEntry).where(
                ACEEntry.created_at >= cutoff
            )
            result = await self.db.execute(entry_query)
            entries = result.scalars().all()
            
            # Group by month
            monthly_data = {}
            for entry in entries:
                if entry.created_at:
                    month_key = entry.created_at.strftime("%Y-%m")
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {
                            "entries": 0,
                            "value": 0,
                            "duty": 0
                        }
                    monthly_data[month_key]["entries"] += 1
                    monthly_data[month_key]["value"] += float(entry.entered_value or 0)
                    monthly_data[month_key]["duty"] += float(entry.duty_amount or 0)
            
            # Convert to list
            for month, data in sorted(monthly_data.items())[-months:]:
                trends["monthly_scores"].append({
                    "month": month,
                    "entries": data["entries"],
                    "total_value": round(data["value"], 2),
                    "total_duty": round(data["duty"], 2),
                    "avg_duty_rate": round(
                        (data["duty"] / data["value"] * 100) if data["value"] > 0 else 0, 2
                    )
                })
            
            # Get compliance screen breakdown
            screen_query = select(ComplianceScreen)
            result = await self.db.execute(screen_query)
            screens = result.scalars().all()
            
            # Risk type breakdown
            risk_types = {}
            risk_levels = {}
            
            for screen in screens:
                rtype = screen.screen_type or "other"
                rlevel = screen.risk_level or "unknown"
                
                risk_types[rtype] = risk_types.get(rtype, 0) + 1
                risk_levels[rlevel] = risk_levels.get(rlevel, 0) + 1
            
            trends["risk_type_breakdown"] = [
                {"type": k, "count": v}
                for k, v in sorted(risk_types.items(), key=lambda x: -x[1])
            ]
            
            trends["risk_level_breakdown"] = [
                {"level": k, "count": v}
                for k, v in sorted(risk_levels.items(), key=lambda x: -x[1])
            ]
            
            # Top importers
            importer_stats = {}
            for entry in entries:
                name = entry.importer_name or "Unknown"
                if name not in importer_stats:
                    importer_stats[name] = {"entries": 0, "value": 0}
                importer_stats[name]["entries"] += 1
                importer_stats[name]["value"] += float(entry.entered_value or 0)
            
            trends["importer_breakdown"] = [
                {"name": k, "entries": v["entries"], "value": round(v["value"], 2)}
                for k, v in sorted(importer_stats.items(), key=lambda x: -x[1]["value"])[:10]
            ]
            
        except Exception as e:
            logger.error(f"Error calculating trends: {e}")
        
        return trends
    
    async def get_country_risk_ranking(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get country risk rankings based on entry data and compliance screens.
        """
        from app.models.ace_entry import ACEEntry
        from app.models.reference_data import ComplianceScreen
        
        rankings = []
        
        try:
            # Get entries by country
            entry_query = select(ACEEntry)
            result = await self.db.execute(entry_query)
            entries = result.scalars().all()
            
            country_stats = {}
            for entry in entries:
                country = entry.country_of_origin or "Unknown"
                if country not in country_stats:
                    country_stats[country] = {
                        "country": country,
                        "entries": 0,
                        "total_value": 0,
                        "total_duty": 0,
                        "adcvd_entries": 0,
                        "section_301_entries": 0,
                        "section_232_entries": 0,
                        "risk_score": 0
                    }
                
                stats = country_stats[country]
                stats["entries"] += 1
                stats["total_value"] += float(entry.entered_value or 0)
                stats["total_duty"] += float(entry.duty_amount or 0)
                
                # Check HTS for section 232 (steel/aluminum)
                hts = entry.hts_code or ""
                if hts.startswith("72") or hts.startswith("73"):  # Steel
                    stats["section_232_entries"] += 1
                elif hts.startswith("76"):  # Aluminum
                    stats["section_232_entries"] += 1
            
            # Calculate risk scores
            for country, stats in country_stats.items():
                # Higher risk for:
                # - High-risk countries (China, Russia, etc.)
                # - Section 232 products
                # - High duty rates
                
                risk_score = 0
                
                # Base risk from AD/CVD prone countries
                high_risk_countries = ["CN", "China", "RU", "Russia", "IR", "Iran"]
                if any(c.lower() in country.lower() for c in high_risk_countries):
                    risk_score += 30
                
                # Section 232 entries
                risk_score += stats["section_232_entries"] * 5
                
                # High average duty rate
                if stats["total_value"] > 0:
                    avg_duty_rate = stats["total_duty"] / stats["total_value"]
                    if avg_duty_rate > 0.25:
                        risk_score += 20
                    elif avg_duty_rate > 0.10:
                        risk_score += 10
                
                stats["risk_score"] = risk_score
                stats["total_value"] = round(stats["total_value"], 2)
                stats["total_duty"] = round(stats["total_duty"], 2)
                
                rankings.append(stats)
            
            # Sort by risk score
            rankings.sort(key=lambda x: -x["risk_score"])
            
        except Exception as e:
            logger.error(f"Error calculating country rankings: {e}")
        
        return rankings[:limit]


# Standalone functions for API routes

async def calculate_compliance_score(
    db: AsyncSession,
    importer_name: str = None,
    period_days: int = 365
) -> Dict[str, Any]:
    """Calculate compliance score for an importer."""
    service = ComplianceScorecardService(db)
    return await service.calculate_importer_score(
        importer_name=importer_name,
        period_days=period_days
    )


async def get_compliance_trends(db: AsyncSession, months: int = 12) -> Dict[str, Any]:
    """Get compliance trends over time."""
    service = ComplianceScorecardService(db)
    return await service.get_compliance_trends(months=months)


async def get_country_risk_ranking(db: AsyncSession, limit: int = 20) -> List[Dict[str, Any]]:
    """Get country risk rankings."""
    service = ComplianceScorecardService(db)
    return await service.get_country_risk_ranking(limit=limit)
