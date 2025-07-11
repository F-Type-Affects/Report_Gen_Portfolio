"""
Google Search Service for AHJ Building Code Searches

This module provides a streamlined Google Custom Search implementation
specifically designed for web application integration. It focuses on
finding building code amendments and AHJ information with optimized
ranking for civil engineering use.

Date: July 2025
"""

import requests
import logging
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import quote_plus
from dataclasses import dataclass, asdict
from datetime import datetime
import time
from app.core.config import get_config
import os

config = get_config()

# Configure logging for web application (errors only)
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Simplified search result for web application use.
    
    Attributes:
        title: The title of the search result
        link: The URL of the search result
        snippet: A short description of the content
        file_format: File format if available (PDF, etc.)
        relevance_score: Internal relevance score for ranking
        priority_tier: Priority tier (1-5) for display
    """
    title: str
    link: str
    snippet: str
    file_format: Optional[str] = None
    relevance_score: float = 0.0
    priority_tier: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class GoogleSearchService:
    """
    Google Search Service optimized for AHJ building code searches.
    
    This service integrates with the web application's architecture and
    provides ranked results prioritizing ICC Digital Codes and Municode.
    """
    
    # API Configuration
    BASE_URL = config.GOOGLE_BASE_URL
    MAX_RESULTS = 10  # Google's maximum per request
    DEFAULT_TIMEOUT = 30
    
    # Priority patterns for ranking
    ICC_PATTERNS = ['codes.iccsafe.org', 'iccsafe.org/codes']
    MUNICODE_PATTERNS = ['library.municode.com', 'municode.com', 'ecode360.com']
    GOV_PATTERNS = ['.gov', '.us']
    
    # Building-related keywords for content analysis
    BUILDING_KEYWORDS = [
        'building code', 'building regulations', 'ibc', 
        'international building code', 'construction code',
        'building safety', 'building department'
    ]
    
    def __init__(self, api_key: str, search_engine_id: str):
        """
        Initialize the Google Search Service.
        
        Args:
            api_key: Google API key
            search_engine_id: Custom Search Engine ID
            
        Raises:
            ValueError: If credentials are missing
        """
        api_key = config.GOOGLE_API_KEY
        search_engine_id = config.GOOGLE_SEARCH_ENGINE_ID
        
        if not api_key or not search_engine_id:
            raise ValueError("API key and Search Engine ID are required")
            
        self.api_key = api_key.strip()
        self.search_engine_id = search_engine_id.strip()
        
        # Create session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AHJ-Search-Service/1.0',
            'Accept': 'application/json'
        })
        
        logger.info("Google Search Service initialized")
    
    def search_ahj_amendments(self, ahj_name: str, state: str) -> List[SearchResult]:
        """
        Search for building code amendments for a specific AHJ.
        
        This is the main method called by the web application. It performs
        an optimized search and returns ranked results.
        
        Args:
            ahj_name: Authority Having Jurisdiction name (e.g., "Scottsdale")
            state: State name or abbreviation (e.g., "Arizona", "AZ")
            
        Returns:
            List of SearchResult objects, ranked by relevance (max 10)
            
        Raises:
            Exception: If the search fails
        """
        if not ahj_name or not state:
            logger.warning("Missing AHJ name or state for search")
            return []
        
        try:
            # Build optimized query
            query = self._build_query(ahj_name.strip(), state.strip())
            
            # Execute search
            raw_results = self._execute_search(query)
            
            # Parse and rank results
            search_results = self._parse_results(raw_results)
            ranked_results = self._rank_results(search_results, ahj_name, state)
            
            logger.info(f"Found {len(ranked_results)} results for {ahj_name}, {state}")
            return ranked_results
            
        except Exception as e:
            logger.error(f"Search failed for {ahj_name}, {state}: {str(e)}")
            # Return empty list instead of raising to prevent route failure
            return []
    
    def _build_query(self, ahj_name: str, state: str) -> str:
        """
        Build an optimized search query for building codes.
        
        Args:
            ahj_name: AHJ name
            state: State name
            
        Returns:
            Optimized query string
        """
        # Use the format that works best for finding official sources
        base_query = f'"{ahj_name}" "{state}" building code'
        
        # Add terms that help find amendments and recent updates
        additional_terms = 'amendments OR IBC OR ordinance OR adopted OR regulations'
        
        return f'{base_query} {additional_terms}'
    
    def _execute_search(self, query: str) -> Dict[str, Any]:
        """
        Execute the Google Custom Search API request.
        
        Args:
            query: Search query string
            
        Returns:
            Raw API response as dictionary
            
        Raises:
            Exception: If the API request fails
        """
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': self.MAX_RESULTS,
            'lr': 'lang_en',      # English results
            'gl': 'us',           # US geographic location
            'safe': 'off',        # Don't filter
            'dateRestrict': 'y3'  # Last 3 years for recent updates
        }
        
        try:
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json()
            
            # Handle specific error cases
            if response.status_code == 403:
                error_msg = "API quota exceeded or invalid credentials"
                logger.error(f"{error_msg}: {response.text}")
                raise Exception(error_msg)
            
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded"
                logger.error(f"{error_msg}: {response.text}")
                raise Exception(error_msg)
            
            else:
                error_msg = f"API request failed with status {response.status_code}"
                logger.error(f"{error_msg}: {response.text}")
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            logger.error("Search request timed out")
            raise Exception("Search request timed out")
        
        except requests.exceptions.ConnectionError:
            logger.error("Connection error during search")
            raise Exception("Connection error - please check internet connection")
    
    def _parse_results(self, response_data: Dict[str, Any]) -> List[SearchResult]:
        """
        Parse raw API response into SearchResult objects.
        
        Args:
            response_data: Raw API response
            
        Returns:
            List of SearchResult objects
        """
        results = []
        items = response_data.get('items', [])
        
        for item in items:
            try:
                # Extract file format if present
                file_format = None
                if 'fileFormat' in item:
                    file_format = item['fileFormat']
                elif item.get('link', '').lower().endswith('.pdf'):
                    file_format = 'PDF'
                
                result = SearchResult(
                    title=item.get('title', ''),
                    link=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                    file_format=file_format
                )
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Error parsing result item: {str(e)}")
                continue
        
        return results
    
    def _rank_results(self, results: List[SearchResult], 
                     ahj_name: str, state: str) -> List[SearchResult]:
        """
        Rank search results by relevance for civil engineering use.
        
        Priority order:
        1. ICC Digital Codes (Tier 1)
        2. Municode with building content (Tier 2)
        3. Other Municode content (Tier 3)
        4. Government sources (Tier 4)
        5. Other sources (Tier 5)
        
        Args:
            results: List of search results to rank
            ahj_name: AHJ name for relevance checking
            state: State name for relevance checking
            
        Returns:
            Ranked list of SearchResult objects
        """
        for result in results:
            score = 0.0
            tier = 5
            
            url_lower = result.link.lower()
            content_lower = f"{result.title} {result.snippet}".lower()
            
            # Tier 1: ICC Digital Codes (highest priority)
            if any(pattern in url_lower for pattern in self.ICC_PATTERNS):
                score = 1.0
                tier = 1
            
            # Tier 2: Municode with building content
            elif any(pattern in url_lower for pattern in self.MUNICODE_PATTERNS):
                # Check for building-related content
                building_score = sum(1 for keyword in self.BUILDING_KEYWORDS 
                                   if keyword in content_lower)
                
                if building_score > 0:
                    score = 0.9
                    tier = 2
                else:
                    score = 0.7
                    tier = 3
            
            # Tier 4: Government sources
            elif any(pattern in url_lower for pattern in self.GOV_PATTERNS):
                score = 0.5
                tier = 4
            
            # Additional scoring for all results
            else:
                score = 0.3
            
            # Boost score for relevant content
            if ahj_name.lower() in content_lower:
                score += 0.05
            
            if state.lower() in content_lower:
                score += 0.05
            
            # Check for recent updates
            update_keywords = ['adopted', 'ordinance', 'effective', 'amended']
            update_score = sum(0.02 for keyword in update_keywords 
                             if keyword in content_lower)
            score += min(update_score, 0.1)
            
            # Set the calculated values
            result.relevance_score = min(score, 1.0)
            result.priority_tier = tier
        
        # Sort by relevance score (highest first)
        ranked_results = sorted(results, 
                              key=lambda x: x.relevance_score, 
                              reverse=True)
        
        return ranked_results
    
    def close(self):
        """Close the HTTP session."""
        if hasattr(self, 'session'):
            self.session.close()
            logger.debug("Google Search Service session closed")
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()


# Helper function for backward compatibility
def perform_google_search(query: str, api_key: str, search_engine_id: str, 
                         retries: int = 3) -> Tuple[List[Dict], List[Dict]]:
    """
    Legacy compatibility function that mimics the old Bing search interface.
    
    This function is provided to ease migration from Bing to Google search.
    It returns results in a format compatible with existing code.
    
    Args:
        query: Search query string
        api_key: Google API key
        search_engine_id: Custom Search Engine ID
        retries: Number of retries (kept for compatibility but not used)
        
    Returns:
        Tuple of (pdf_links, web_links) where each is a list of dicts
        with 'name' and 'url' keys
    """
    try:
        service = GoogleSearchService(api_key, search_engine_id)
        
        # Parse AHJ name and state from query if possible
        # Expected format: "AHJ Name, State building code amendments"
        parts = query.split(',')
        if len(parts) >= 2:
            ahj_name = parts[0].strip()
            state_part = parts[1].strip()
            state = state_part.split()[0] if state_part else ""
        else:
            # Fallback: use the whole query
            ahj_name = query
            state = ""
        
        # Perform search
        results = service.search_ahj_amendments(ahj_name, state)
        
        # Convert to legacy format
        pdf_links = []
        web_links = []
        
        for result in results:
            link_data = {
                'name': result.title,
                'url': result.link
            }
            
            # Separate PDFs and web links for backward compatibility
            if result.file_format == 'PDF' or result.link.lower().endswith('.pdf'):
                pdf_links.append(link_data)
            else:
                web_links.append(link_data)
        
        service.close()
        return pdf_links, web_links
        
    except Exception as e:
        logger.error(f"Google search failed: {str(e)}")
        return [], []