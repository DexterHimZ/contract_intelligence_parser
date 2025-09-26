import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from dateutil.relativedelta import relativedelta
import dateutil.parser

logger = logging.getLogger(__name__)


@dataclass
class ExtractionPattern:
    name: str
    patterns: List[str]
    processor: Optional[callable] = None
    confidence_base: float = 0.5


class ContractPatterns:
    """Comprehensive regex patterns for contract extraction"""

    @staticmethod
    def compile_patterns() -> Dict[str, ExtractionPattern]:
        return {
            # Party Identification
            "party_1_name": ExtractionPattern(
                name="party_1_name",
                patterns=[
                    r"(?i)(?:between|by\s+and\s+between)\s+([A-Z][A-Za-z\s&,.\-]+?)(?:\s+\(|,|\s+a\s+|\s+and\b)",
                    r"(?i)^This\s+(?:Agreement|Contract).*?by\s+and\s+between\s+([A-Z][A-Za-z\s&,.\-]+?)(?:\s+\(|,)",
                    r"(?i)(?:Client|Customer|Buyer|Purchaser):\s*([A-Z][A-Za-z\s&,.\-]+?)(?:\n|,|\()",
                    r'"Party A"[:\s]+means\s+([A-Z][A-Za-z\s&,.\-]+?)(?:\s+\(|,|\s+and\b)',
                ],
                confidence_base=0.6
            ),
            "party_2_name": ExtractionPattern(
                name="party_2_name",
                patterns=[
                    r"(?i)(?:between.*?and|,\s+and)\s+([A-Z][A-Za-z\s&,.\-]+?)(?:\s+\(|,|\s+\)|$)",
                    r"(?i)(?:Vendor|Supplier|Seller|Provider|Contractor):\s*([A-Z][A-Za-z\s&,.\-]+?)(?:\n|,|\()",
                    r'"Party B"[:\s]+means\s+([A-Z][A-Za-z\s&,.\-]+?)(?:\s+\(|,|\s+and\b)',
                ],
                confidence_base=0.6
            ),

            # Dates
            "effective_date": ExtractionPattern(
                name="effective_date",
                patterns=[
                    r"(?i)\b(?:effective|commencement|start)\s+date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)effective\s+as\s+of\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)shall\s+commence\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    # Enhanced patterns for invoice-style contracts
                    r"(?i)(?:agreement\s+)?(?:effective|executed|signed|dated)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)this\s+(?:agreement|contract).*?(?:dated|executed|signed)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)(?:contract|agreement)\s+date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)dated\s+this\s+\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+,?\s+\d{4})",
                    r"(?i)executed\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                ],
                processor=lambda x: ContractPatterns._parse_date(x),
                confidence_base=0.7
            ),
            "execution_date": ExtractionPattern(
                name="execution_date",
                patterns=[
                    r"(?i)(?:executed|signed|dated)\s+(?:this|on)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)date\s+of\s+execution[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                ],
                processor=lambda x: ContractPatterns._parse_date(x),
                confidence_base=0.65
            ),
            "termination_date": ExtractionPattern(
                name="termination_date",
                patterns=[
                    r"(?i)(?:terminat|expir|end)(?:es|ing|ation)?\s+(?:on|date)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)through\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)until\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    # Enhanced patterns for various termination date formats
                    r"(?i)(?:contract|agreement)\s+(?:terminates|expires|ends)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)(?:expiry|expiration)\s+date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)end\s+date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)valid\s+(?:until|through)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    r"(?i)contract\s+period[:\s]+.*?(?:to|until|through)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                ],
                processor=lambda x: ContractPatterns._parse_date(x),
                confidence_base=0.65
            ),
            "contract_term": ExtractionPattern(
                name="contract_term",
                patterns=[
                    r"(?i)contract\s+term[:\s]+(\d+\s+(?:months?|years?))",
                    r"(?i)(?:term|period)\s+of\s+(\d+\s+(?:months?|years?))",
                    r"(?i)for\s+a\s+(?:term|period)\s+of\s+(\d+\s+(?:months?|years?))",
                    r"(?i)(\d+[-\s](?:month|year)s?)\s+(?:term|period|contract)",
                ],
                confidence_base=0.7
            ),

            # Financial Details
            "contract_value": ExtractionPattern(
                name="contract_value",
                patterns=[
                    r"(?i)total\s+(?:contract\s+)?(?:value|amount|price)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)(?:contract|total)\s+(?:sum|consideration)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)(?:annual\s+contract\s+value|total\s+annual\s+value|acv)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)annual\s+contract\s+value[:\s]+\$?([\d,]+(?:\.\d{2})?)(?:\s+\+[^=]*)?(?:\s*=\s*\$?([\d,]+(?:\.\d{2})?))?",
                    r"(?i)total\s+annual\s+value[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)total\s+monthly\s+amount[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)monthly\s+(?:fee|payment|amount)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    # REMOVED: Generic USD/dollars pattern that captures first amounts
                    # REMOVED: Generic \"for the sum of\" pattern
                    # Enhanced patterns for invoice-style totals
                    # REMOVED: Total due pattern - handled by enhanced extraction
                    # REMOVED: Generic total pattern - handled by enhanced extraction
                    # REMOVED: Generic invoice total pattern - handled by enhanced extraction
                ],
                processor=lambda x: ContractPatterns._parse_money(x),
                confidence_base=0.7
            ),
            "currency": ExtractionPattern(
                name="currency",
                patterns=[
                    r"(?i)\b(USD|EUR|GBP|INR|CAD|AUD|CNY|JPY)\b",
                    r"(?i)\b(dollars|euros|pounds|rupees)\b",
                    r"([$€£₹¥])",
                ],
                processor=lambda x: ContractPatterns._normalize_currency(x),
                confidence_base=0.8
            ),
            "payment_terms": ExtractionPattern(
                name="payment_terms",
                patterns=[
                    r"(?i)payment\s+terms[:\s]+([^\n]+)",
                    r"(?i)\bnet\s+(\d+)\s*(?:days)?\b",
                    r"(?i)payment\s+(?:is\s+)?due\s+(?:within\s+)?(\d+)\s+days",
                    r"(?i)(\d+)\s+days\s+(?:from|after)\s+(?:invoice|receipt)",
                ],
                confidence_base=0.65
            ),
            "billing_frequency": ExtractionPattern(
                name="billing_frequency",
                patterns=[
                    # GUARD: Only explicit recurring billing patterns - VERY restrictive to avoid late fee confusion
                    r"(?i)\b(monthly|quarterly|annually|yearly|weekly|bi-weekly|semi-annually)\s+(?:billing|payment|invoice)\s+(?:schedule|cycle|frequency)",
                    r"(?i)(?:billed|invoiced|paid)\s+(monthly|quarterly|annually|yearly|weekly)\s+(?:in\s+advance|recurring)",
                    r"(?i)(?:recurring|subscription)\s+(?:billing|payment)\s*:\s*(monthly|quarterly|annually|yearly|weekly)",
                    r"(?i)billing\s+cycle\s*:\s*(monthly|quarterly|annually|yearly|weekly)",
                    r"(?i)subscription\s+(?:billing|payment)\s*:\s*(monthly|quarterly|annually|yearly|weekly)",
                    # Only explicit billing context - no generic "per month" patterns
                ],
                confidence_base=0.8  # Higher threshold for explicit billing only
            ),

            # Legal Terms
            "governing_law": ExtractionPattern(
                name="governing_law",
                patterns=[
                    r"(?i)governed\s+by\s+(?:the\s+)?laws?\s+of\s+(?:the\s+)?(?:state\s+of\s+)?([A-Za-z\s]+?)(?:\.|,|\n)",
                    r"(?i)(?:applicable|governing)\s+law[:\s]+([A-Za-z\s]+?)(?:\.|,|\n)",
                    r"(?i)subject\s+to\s+(?:the\s+)?(?:exclusive\s+)?jurisdiction\s+of\s+([A-Za-z\s]+?)(?:\.|,|\n)",
                    # Enhanced patterns for governing law
                    r"(?i)governing\s+law[:\s]+(?:this\s+(?:agreement|contract)\s+(?:shall\s+be\s+)?)?(?:governed\s+by\s+)?(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+)?(?:state\s+of\s+)?([A-Za-z\s]+?)(?:\.|,|\n|dispute)",
                    r"(?i)this\s+(?:agreement|contract).*?(?:governed|subject)\s+to.*?(?:laws?\s+of\s+)?(?:the\s+)?(?:state\s+of\s+)?([A-Za-z\s]+?)(?:\.|,|\n)",
                    r"(?i)laws?\s+of\s+(?:the\s+)?(?:state\s+of\s+)?([A-Za-z\s]+?)\s+(?:shall\s+)?(?:apply|govern)",
                    r"(?i)jurisdiction[:\s]+([A-Za-z\s]+?)(?:\.|,|\n|court)",
                    r"(?i)disputes.*?(?:governed|resolved).*?(?:in\s+)?(?:the\s+)?(?:state\s+of\s+)?([A-Za-z\s]+?)(?:\.|,|\n)",
                ],
                confidence_base=0.75
            ),
            "liability_cap": ExtractionPattern(
                name="liability_cap",
                patterns=[
                    r"(?i)liability.*?(?:shall\s+not\s+exceed|limited\s+to|cap(?:ped)?\s+at)\s+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)maximum\s+liability.*?\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)aggregate\s+liability.*?\$?([\d,]+(?:\.\d{2})?)",
                    # Enhanced patterns for liability caps
                    r"(?i)liability.*?(?:capped|limited|restricted|maximum).*?\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)(?:total|aggregate|maximum)\s+(?:damages|liability).*?\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)liability\s+(?:is\s+)?limited\s+to\s+(?:a\s+maximum\s+of\s+)?\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)damages.*?(?:shall\s+not\s+exceed|limited\s+to|maximum\s+of)\s+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)(?:cap\s+on\s+)?(?:damages|liability)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
                    r"(?i)liability.*?(?:up\s+to|not\s+to\s+exceed)\s+\$?([\d,]+(?:\.\d{2})?)",
                    # Pattern for percentage-based caps
                    r"(?i)liability.*?limited\s+to\s+(\d+)\s+months?\s+of\s+(?:fees|payments?)",
                ],
                processor=lambda x: ContractPatterns._parse_money(x),
                confidence_base=0.65
            ),
            "confidentiality": ExtractionPattern(
                name="confidentiality",
                patterns=[
                    r"(?i)(confidential(?:ity)?|non-disclosure|NDA)(?:\s+(?:clause|provision|agreement))?",
                    r"(?i)shall\s+(?:keep|maintain|treat\s+as)\s+confidential",
                    r"(?i)proprietary\s+and\s+confidential\s+information",
                ],
                processor=lambda x: True if x else False,
                confidence_base=0.8
            ),

            # Renewal Terms
            "auto_renewal": ExtractionPattern(
                name="auto_renewal",
                patterns=[
                    r"(?i)\bauto(?:matic(?:ally)?)?\s*renew(?:al|s|ed)?\b",
                    r"(?i)\bauto[-\s]renews?\b",
                    r"(?i)auto-renewal",
                    r"(?i)shall\s+automatically\s+renew",
                    r"(?i)contract\s+auto[-\s]renews?",
                    r"(?i)unless.*?(?:terminated|cancelled).*?automatically\s+renew",
                    r"(?i)contract\s+auto-renews\s+for\s+additional",
                    r"(?i)auto-renewal[:\s]+yes",
                    r"(?i)auto-renewal[:\s]+true",
                    # Enhanced patterns for auto-renewal detection
                    r"(?i)(?:contract|agreement)\s+(?:shall\s+)?(?:automatically\s+)?renew(?:s)?(?:\s+(?:for|automatically))?",
                    r"(?i)(?:renew|extend)(?:al|s)?\s+(?:automatic(?:ally)?|auto)",
                    r"(?i)(?:automatically\s+)?(?:renew|extend)(?:s|ed|ing)?\s+(?:for\s+)?(?:additional|successive|further)\s+(?:term|period)",
                    r"(?i)(?:term|contract)\s+(?:shall\s+)?(?:be\s+)?(?:automatically\s+)?(?:renewed|extended)",
                    r"(?i)unless\s+(?:either\s+party\s+)?(?:provides?\s+)?(?:written\s+)?notice.*?(?:renew|extend)",
                    r"(?i)renewal[:\s]+(?:automatic|yes|true)",
                ],
                processor=lambda x: True if x else False,
                confidence_base=0.75
            ),
            "renewal_term": ExtractionPattern(
                name="renewal_term",
                patterns=[
                    r"(?i)renew.*?for\s+(?:an?\s+)?(?:additional\s+)?(\d+)\s+(year|month|day)s?",
                    r"(?i)renewal\s+(?:term|period)[:\s]+(\d+)\s+(year|month|day)s?",
                    r"(?i)(?:successive|additional)\s+(?:term|period)s?\s+of\s+(\d+)\s+(year|month|day)s?",
                ],
                confidence_base=0.65
            ),
            "notice_period": ExtractionPattern(
                name="notice_period",
                patterns=[
                    r"(?i)(\d+)\s+days?\s+(?:written\s+)?notice",
                    r"(?i)notice\s+(?:period|of)[:\s]+(\d+)\s+days?",
                    r"(?i)at\s+least\s+(\d+)\s+days?\s+(?:prior\s+)?(?:written\s+)?notice",
                    # Enhanced patterns for notice periods
                    r"(?i)(?:with\s+)?(\d+)\s+days?\s+(?:prior\s+)?(?:written\s+)?notice\s+(?:of\s+termination|to\s+terminate)",
                    r"(?i)terminate.*?(?:with\s+)?(\d+)\s+days?\s+(?:advance\s+)?(?:written\s+)?notice",
                    r"(?i)(?:written\s+)?notice\s+of\s+(?:at\s+least\s+)?(\d+)\s+days?",
                    r"(?i)(\d+)\s+days?\s+(?:advance\s+)?(?:written\s+)?notice\s+(?:prior\s+to|before)",
                    r"(?i)(?:minimum|required)\s+notice[:\s]+(\d+)\s+days?",
                    r"(?i)notice\s+requirement[:\s]+(\d+)\s+days?",
                    r"(?i)(\d+)\s+days?\s+notice\s+(?:shall\s+be\s+)?(?:given|provided|required)",
                ],
                confidence_base=0.7
            ),

            # Service Level Agreement
            "sla_uptime": ExtractionPattern(
                name="sla_uptime",
                patterns=[
                    r"(?i)uptime.*?(\d+(?:\.\d+)?)\s*%",
                    r"(?i)availability.*?(\d+(?:\.\d+)?)\s*%",
                    r"(?i)(\d+(?:\.\d+)?)\s*%\s+(?:uptime|availability)",
                ],
                processor=lambda x: float(x) if x else None,
                confidence_base=0.75
            ),
            "support_hours": ExtractionPattern(
                name="support_hours",
                patterns=[
                    r"(?i)support.*?(\d+)\s*[x×]\s*(\d+)",
                    r"(?i)(?:24[/x×]7|24\s+hours)",
                    r"(?i)business\s+hours.*?(\d+:\d+.*?\d+:\d+)",
                ],
                confidence_base=0.65
            ),

            # Termination
            "termination_for_convenience": ExtractionPattern(
                name="termination_for_convenience",
                patterns=[
                    r"(?i)terminat\w+\s+(?:for\s+)?convenience",
                    r"(?i)either\s+party\s+may\s+terminate",
                    r"(?i)without\s+cause.*?terminat",
                ],
                processor=lambda x: True if x else False,
                confidence_base=0.7
            ),
            "termination_for_cause": ExtractionPattern(
                name="termination_for_cause",
                patterns=[
                    r"(?i)terminat\w+\s+for\s+cause",
                    r"(?i)material\s+breach.*?terminat",
                    r"(?i)default.*?terminat",
                ],
                processor=lambda x: True if x else False,
                confidence_base=0.7
            ),

            # Signature and Contact Information
            "signatory_1_name": ExtractionPattern(
                name="signatory_1_name",
                patterns=[
                    r"(?i)(?:for\s+.*?\n)?name\s*:\s*([A-Za-z\s.]+?)(?:\n|title|signature)",
                    r"(?i)authorized\s+representative\s*:\s*([A-Za-z\s.]+?)(?:\n|$)",
                    r"(?i)signed\s+by\s*:\s*([A-Za-z\s.]+?)(?:\n|$)",
                ],
                confidence_base=0.7
            ),
            "signatory_1_title": ExtractionPattern(
                name="signatory_1_title",
                patterns=[
                    r"(?i)title\s*:\s*([A-Za-z\s.]+?)(?:\n|signature)",
                    r"(?i)([A-Za-z\s]+(?:director|manager|head|lead|officer))\s*(?:\n|$)",
                ],
                confidence_base=0.65
            ),
            "signatory_2_name": ExtractionPattern(
                name="signatory_2_name",
                patterns=[
                    r"(?i)(?:for\s+.*?\n.*?name\s*:\s*[^\n]+\n.*?){1}name\s*:\s*([A-Za-z\s.]+?)(?:\n|title|signature)",
                ],
                confidence_base=0.7
            ),
            "signatory_2_title": ExtractionPattern(
                name="signatory_2_title",
                patterns=[
                    r"(?i)(?:for\s+.*?\n.*?title\s*:\s*[^\n]+\n.*?){1}title\s*:\s*([A-Za-z\s.]+?)(?:\n|signature)",
                ],
                confidence_base=0.65
            ),

            # Contact Information
            "primary_contact_name": ExtractionPattern(
                name="primary_contact_name",
                patterns=[
                    r"(?i)primary\s+contact\s*:\s*([A-Za-z\s.]+?)(?:\s+\([^)]+\)|—|$)",
                    r"(?i)contact\s*:\s*([A-Za-z\s.]+?)(?:\s+\([^)]+\)|—|$)",
                ],
                confidence_base=0.8
            ),
            "primary_contact_email": ExtractionPattern(
                name="primary_contact_email",
                patterns=[
                    r"(?i)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                ],
                confidence_base=0.9
            ),
            "customer_address": ExtractionPattern(
                name="customer_address",
                patterns=[
                    r"(?i)(?:customer\s+)?address\s*:\s*([^,\n]+,\s*[^,\n]+,\s*[^,\n]+)",
                    r"(?i)(\d+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?,\s*[A-Z]{2,3})",
                ],
                confidence_base=0.8
            ),
        }

    @staticmethod
    def _parse_date(date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        try:
            if date_str:
                parsed = dateutil.parser.parse(date_str)
                return parsed.strftime("%Y-%m-%d")
        except:
            pass
        return date_str

    @staticmethod
    def _parse_money(money_str: str) -> Optional[float]:
        """Parse money string to float"""
        try:
            if money_str:
                # Remove currency symbols and commas
                cleaned = re.sub(r'[,$£€₹]', '', money_str)
                return float(cleaned)
        except:
            pass
        return None

    @staticmethod
    def _normalize_currency(currency_str: str) -> str:
        """Normalize currency to ISO code"""
        currency_map = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "₹": "INR",
            "¥": "JPY",
            "dollars": "USD",
            "euros": "EUR",
            "pounds": "GBP",
            "rupees": "INR",
        }
        return currency_map.get(currency_str.lower(), currency_str.upper())

    @staticmethod
    def _convert_monthly_to_annual(monthly_value: float) -> float:
        """Convert monthly contract value to annual"""
        if isinstance(monthly_value, (int, float)):
            return monthly_value * 12
        return monthly_value

    @staticmethod
    def _add_months_to_date(date_str: str, months: int) -> Optional[str]:
        """Add months to a date string and return ISO format"""
        try:
            if date_str:
                parsed = dateutil.parser.parse(date_str)
                # Add months using relativedelta for accurate date arithmetic
                new_date = parsed + relativedelta(months=months)
                return new_date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.debug(f"Error adding months to date: {e}")
            pass
        return None

    @staticmethod
    def _add_years_to_date(date_str: str, years: int) -> Optional[str]:
        """Add years to a date string and return ISO format"""
        try:
            if date_str:
                parsed = dateutil.parser.parse(date_str)
                new_date = parsed + relativedelta(years=years)
                return new_date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.debug(f"Error adding years to date: {e}")
            pass
        return None

    @staticmethod
    def derive_termination_date(effective_date: str, contract_term: str) -> Tuple[Optional[str], float]:
        """Derive termination date from effective date and contract term"""
        if not effective_date or not contract_term:
            return None, 0.0

        try:
            # Parse contract term to extract number and unit
            import re
            term_match = re.search(r'(\d+)\s+(months?|years?)', contract_term, re.IGNORECASE)
            if not term_match:
                return None, 0.0

            number = int(term_match.group(1))
            unit = term_match.group(2).lower()

            if 'month' in unit:
                result = ContractPatterns._add_months_to_date(effective_date, number)
            elif 'year' in unit:
                result = ContractPatterns._add_years_to_date(effective_date, number)
            else:
                return None, 0.0

            return result, 0.75 if result else 0.0  # Medium confidence for derived values

        except Exception as e:
            logger.error(f"Error deriving termination date: {e}")
            return None, 0.0

    @staticmethod
    def extract_field(text: str, pattern: ExtractionPattern) -> Tuple[Any, float, str]:
        """Extract field using pattern and return value, confidence, and evidence"""
        for regex_pattern in pattern.patterns:
            matches = re.finditer(regex_pattern, text, re.MULTILINE | re.DOTALL)
            for match in matches:
                value = match.group(1) if match.groups() else match.group(0)

                # Apply processor if available
                if pattern.processor:
                    value = pattern.processor(value)

                if value is not None:
                    # Calculate confidence based on match quality
                    confidence = pattern.confidence_base

                    # Special handling for contract_value extraction
                    if pattern.name == "contract_value":
                        # Handle "Annual Contract Value: $X + $Y = $Z" pattern
                        if "annual contract value" in match.group(0).lower() and "=" in match.group(0):
                            # Extract the final value after the equals sign
                            equals_match = re.search(r'=\s*\$?([\d,]+(?:\.\d{2})?)', match.group(0))
                            if equals_match:
                                value = ContractPatterns._parse_money(equals_match.group(1))
                        # Check if this is a monthly amount that needs conversion
                        elif "monthly" in match.group(0).lower():
                            value = ContractPatterns._convert_monthly_to_annual(value)
                            confidence = 0.75  # Lower confidence for derived values

                        # Set confidence based on extraction type
                        if "annual" in match.group(0).lower() or "total" in match.group(0).lower():
                            confidence = 0.9  # High confidence for explicit annual values
                        else:
                            confidence = 0.85

                    # Boost confidence for exact matches
                    if match.group(0).strip() == str(value):
                        confidence += 0.1

                    # Get snippet for evidence
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    snippet = text[start:end].replace('\n', ' ').strip()

                    return value, min(confidence, 1.0), snippet

        return None, 0.0, ""