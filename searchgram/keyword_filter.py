"""
Keyword Filter for Channel Mirroring

Supports whitelist/blacklist filtering for message content.
"""

import logging
import re
from typing import List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of keyword filtering."""
    should_mirror: bool
    reason: Optional[str] = None
    matched_keywords: Optional[List[str]] = None


class KeywordFilter:
    """
    Keyword-based message filter with whitelist/blacklist support.

    Filtering logic:
    1. Blacklist check (highest priority): If any blacklist keyword matches, block
    2. Whitelist check: If whitelist is configured, require at least one match
    3. No filters: Allow all messages
    """

    def __init__(
        self,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        case_sensitive: bool = False,
        use_regex: bool = False
    ):
        """
        Initialize keyword filter.

        Args:
            whitelist: List of required keywords (allow only if matched)
            blacklist: List of blocked keywords (block if matched)
            case_sensitive: Enable case-sensitive matching
            use_regex: Treat keywords as regex patterns
        """
        self.whitelist = self._prepare_keywords(whitelist or [])
        self.blacklist = self._prepare_keywords(blacklist or [])
        self.case_sensitive = case_sensitive
        self.use_regex = use_regex

        # Compile regex patterns if needed
        if self.use_regex:
            self.whitelist_patterns = self._compile_patterns(self.whitelist)
            self.blacklist_patterns = self._compile_patterns(self.blacklist)

    def _prepare_keywords(self, keywords: List[str]) -> Set[str]:
        """
        Prepare keywords for matching.

        Args:
            keywords: Raw keyword list

        Returns:
            Set of prepared keywords
        """
        if not self.case_sensitive:
            return {kw.lower() for kw in keywords if kw}
        return {kw for kw in keywords if kw}

    def _compile_patterns(self, keywords: Set[str]) -> List[re.Pattern]:
        """
        Compile regex patterns from keywords.

        Args:
            keywords: Set of regex pattern strings

        Returns:
            List of compiled regex patterns
        """
        patterns = []
        flags = 0 if self.case_sensitive else re.IGNORECASE

        for kw in keywords:
            try:
                pattern = re.compile(kw, flags)
                patterns.append(pattern)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{kw}': {e}")

        return patterns

    def check(self, text: str) -> FilterResult:
        """
        Check if text should be mirrored based on keyword filters.

        Args:
            text: Text to check

        Returns:
            FilterResult with decision and details
        """
        if not text or not text.strip():
            logger.debug("Empty text provided to keyword filter")
            return FilterResult(should_mirror=True, reason="empty_text")

        # Prepare text for matching
        check_text = text if self.case_sensitive else text.lower()

        # Check blacklist (highest priority)
        if self.blacklist:
            blacklist_matches = self._find_matches(check_text, self.blacklist,
                                                   self.blacklist_patterns if self.use_regex else None)
            if blacklist_matches:
                logger.info(f"Blacklist keywords matched: {blacklist_matches}")
                return FilterResult(
                    should_mirror=False,
                    reason="blacklist",
                    matched_keywords=list(blacklist_matches)
                )

        # Check whitelist (if configured)
        if self.whitelist:
            whitelist_matches = self._find_matches(check_text, self.whitelist,
                                                   self.whitelist_patterns if self.use_regex else None)
            if whitelist_matches:
                logger.debug(f"Whitelist keywords matched: {whitelist_matches}")
                return FilterResult(
                    should_mirror=True,
                    reason="whitelist",
                    matched_keywords=list(whitelist_matches)
                )
            else:
                logger.info("No whitelist keywords matched, blocking message")
                return FilterResult(
                    should_mirror=False,
                    reason="no_whitelist_match",
                    matched_keywords=[]
                )

        # No filters matched, allow by default
        return FilterResult(should_mirror=True, reason="no_filters")

    def _find_matches(
        self,
        text: str,
        keywords: Set[str],
        patterns: Optional[List[re.Pattern]] = None
    ) -> Set[str]:
        """
        Find matching keywords in text.

        Args:
            text: Text to search
            keywords: Keywords to find
            patterns: Compiled regex patterns (if use_regex=True)

        Returns:
            Set of matched keywords
        """
        matches = set()

        if self.use_regex and patterns:
            # Regex matching
            for pattern in patterns:
                if pattern.search(text):
                    matches.add(pattern.pattern)
        else:
            # Simple substring matching
            for keyword in keywords:
                if keyword in text:
                    matches.add(keyword)

        return matches

    def update_whitelist(self, keywords: List[str]):
        """
        Update whitelist keywords.

        Args:
            keywords: New whitelist keywords
        """
        self.whitelist = self._prepare_keywords(keywords)
        if self.use_regex:
            self.whitelist_patterns = self._compile_patterns(self.whitelist)
        logger.info(f"Updated whitelist: {len(self.whitelist)} keywords")

    def update_blacklist(self, keywords: List[str]):
        """
        Update blacklist keywords.

        Args:
            keywords: New blacklist keywords
        """
        self.blacklist = self._prepare_keywords(keywords)
        if self.use_regex:
            self.blacklist_patterns = self._compile_patterns(self.blacklist)
        logger.info(f"Updated blacklist: {len(self.blacklist)} keywords")

    def add_to_whitelist(self, keyword: str):
        """Add single keyword to whitelist."""
        kw = keyword if self.case_sensitive else keyword.lower()
        self.whitelist.add(kw)
        if self.use_regex:
            self.whitelist_patterns = self._compile_patterns(self.whitelist)

    def add_to_blacklist(self, keyword: str):
        """Add single keyword to blacklist."""
        kw = keyword if self.case_sensitive else keyword.lower()
        self.blacklist.add(kw)
        if self.use_regex:
            self.blacklist_patterns = self._compile_patterns(self.blacklist)

    def remove_from_whitelist(self, keyword: str):
        """Remove single keyword from whitelist."""
        kw = keyword if self.case_sensitive else keyword.lower()
        self.whitelist.discard(kw)
        if self.use_regex:
            self.whitelist_patterns = self._compile_patterns(self.whitelist)

    def remove_from_blacklist(self, keyword: str):
        """Remove single keyword from blacklist."""
        kw = keyword if self.case_sensitive else keyword.lower()
        self.blacklist.discard(kw)
        if self.use_regex:
            self.blacklist_patterns = self._compile_patterns(self.blacklist)

    def get_stats(self) -> dict:
        """
        Get filter statistics.

        Returns:
            Dict with filter stats
        """
        return {
            "whitelist_count": len(self.whitelist),
            "blacklist_count": len(self.blacklist),
            "case_sensitive": self.case_sensitive,
            "use_regex": self.use_regex
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example 1: Whitelist only (crypto-related messages)
    filter1 = KeywordFilter(
        whitelist=["bitcoin", "ethereum", "crypto", "blockchain"],
        case_sensitive=False
    )

    test_messages = [
        "Bitcoin price is up today!",
        "Check out this new recipe",
        "Ethereum 2.0 launch successful"
    ]

    print("=== Whitelist Filter ===")
    for msg in test_messages:
        result = filter1.check(msg)
        print(f"'{msg}' -> {result.should_mirror} ({result.reason})")

    # Example 2: Blacklist only (spam filter)
    filter2 = KeywordFilter(
        blacklist=["free money", "click here", "scam", "win prize"],
        case_sensitive=False
    )

    spam_messages = [
        "Click here for free money!!!",
        "This is a normal message",
        "Win a prize by clicking this link"
    ]

    print("\n=== Blacklist Filter ===")
    for msg in spam_messages:
        result = filter2.check(msg)
        print(f"'{msg}' -> {result.should_mirror} ({result.reason})")

    # Example 3: Combined whitelist and blacklist
    filter3 = KeywordFilter(
        whitelist=["bitcoin", "ethereum"],
        blacklist=["scam", "ponzi"],
        case_sensitive=False
    )

    combined_messages = [
        "Bitcoin is a great investment",
        "Ethereum scam alert!",
        "This ponzi scheme uses bitcoin",
        "Random message about cats"
    ]

    print("\n=== Combined Filter ===")
    for msg in combined_messages:
        result = filter3.check(msg)
        print(f"'{msg}' -> {result.should_mirror} ({result.reason}) {result.matched_keywords}")

    # Example 4: Regex patterns
    filter4 = KeywordFilter(
        whitelist=[r"\d{4}-\d{2}-\d{2}", r"USD?\\$\d+"],  # Dates and prices
        use_regex=True,
        case_sensitive=False
    )

    regex_messages = [
        "Meeting on 2025-01-15 at 3pm",
        "Price is $499",
        "Random message without patterns"
    ]

    print("\n=== Regex Filter ===")
    for msg in regex_messages:
        result = filter4.check(msg)
        print(f"'{msg}' -> {result.should_mirror} ({result.reason})")
